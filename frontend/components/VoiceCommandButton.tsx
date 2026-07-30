"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useVoiceCommand } from "@/hooks/useVoiceCommand";
import { useVoiceMutePreference } from "@/hooks/useVoiceMutePreference";
import VoiceConversationPanel from "@/components/VoiceConversationPanel";

const FAB_SIZE = 56;
const MUTE_TOGGLE_SIZE = 32;

// Routes where the button shouldn't render at all — not disabled, absent —
// since there's no session context worth surfacing on the auth screens
// themselves. app/layout.tsx exports `metadata`, which requires it to stay a
// Server Component, so usePathname() (a client hook) lives here instead;
// this component is already "use client", and the effect is identical either
// way — root layout still controls what renders.
const HIDDEN_ROUTES = ["/login", "/signup"];

export default function VoiceCommandButton() {
  const pathname = usePathname();
  const user = useCurrentUser();
  const { isMuted, toggleMuted } = useVoiceMutePreference();
  // Same client-side auth-state check the rest of the app uses for UI
  // affordances (see hooks/useCurrentUser.ts, lib/auth.ts:isUnrestrictedUser).
  // This only gates the button's appearance — /api/voice/parse/ enforces the
  // real, signed-cookie-based auth server-side regardless of what this shows.
  const isAuthenticated = user !== null;
  const {
    status, interimTranscript, isDisabled, startListening, stopListening,
    submitTranscript, conversation, closeConversation,
  } = useVoiceCommand(isMuted, isAuthenticated);

  // Lets a user open a chat-style box to type the very first command instead
  // of speaking it — opens the same VoiceConversationPanel used for the rest
  // of the exchange (see the "greeting" phase branch below), just ahead of
  // any real conversation existing yet. Local UI-only state (not lifted into
  // useVoiceCommand) since nothing outside this component's render needs it.
  const [isTypedInputOpen, setIsTypedInputOpen] = useState(false);

  if (HIDDEN_ROUTES.includes(pathname)) return null;

  const isListening  = status === "listening";
  const isProcessing = status === "processing";

  const disabledReason = !isAuthenticated
    ? "Log in to use voice commands"
    : "Voice commands need a Chromium-based browser (Chrome, Edge) — the Web Speech API isn't available here.";

  // Typing doesn't need the Web Speech API the mic button requires — only
  // authentication does (the same server-side gate /api/voice/parse/
  // enforces regardless). Gating on isAuthenticated alone, not isDisabled,
  // means this also becomes the working fallback on non-Chromium browsers.
  const canType = isAuthenticated;

  // Every voice response now opens this panel — the recognized transcript
  // while the request is in flight, then the result, whether the intent was
  // conversational or a one-shot. The panel replaces the plain button in
  // place, so it reads as the mic icon expanding rather than a separate
  // destination. Never shown while logged out/unsupported: isDisabled
  // already gates whether a conversation could ever have started (see
  // useVoiceCommand's submitTranscript, which checks the same condition
  // before falling back to a toast).
  if (conversation && !isDisabled) {
    return (
      <VoiceConversationPanel
        transcript={conversation.transcript}
        message={conversation.message}
        phase={conversation.phase}
        conversational={conversation.conversational}
        awaitingInput={conversation.awaitingInput}
        resultStatus={conversation.resultStatus}
        isListening={isListening}
        isProcessing={isProcessing}
        interimTranscript={interimTranscript}
        onStartListening={startListening}
        onStopListening={stopListening}
        onSubmitText={submitTranscript}
        onClose={closeConversation}
        isMuted={isMuted}
        onToggleMute={toggleMuted}
      />
    );
  }

  // Keyboard toggle opens the same panel component in its "greeting" phase —
  // a chat box with a static hello and the typed/mic input controls, open
  // before any real command exists. Submitting from here calls submitTranscript
  // the same as every other entry point, which sets `conversation` and hands
  // rendering back to the branch above for the rest of the exchange.
  //
  // Gated on canType, not isDisabled — same reasoning as canType's own
  // definition above: typing needs only authentication, not Web Speech API
  // support, so this chat box must still open on non-Chromium browsers (the
  // one place typed commands work at all there). On such a browser,
  // submitTranscript's own isDisabled check still routes the *result* to a
  // toast instead of setting `conversation` (see its docstring) — this panel
  // simply stays open afterwards, ready for the next typed command, rather
  // than transitioning to a transcript/result view it can't show there.
  if (isTypedInputOpen && canType) {
    return (
      <VoiceConversationPanel
        transcript=""
        message=""
        phase="greeting"
        conversational={false}
        awaitingInput={false}
        resultStatus={null}
        isListening={isListening}
        isProcessing={isProcessing}
        interimTranscript={interimTranscript}
        onStartListening={startListening}
        onStopListening={stopListening}
        onSubmitText={submitTranscript}
        onClose={() => setIsTypedInputOpen(false)}
        isMuted={isMuted}
        onToggleMute={toggleMuted}
      />
    );
  }

  return (
    <div
      style={{
        position: "fixed", right: 20, bottom: 20, zIndex: 1000,
        display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8,
      }}
    >
      {/* Once processing starts, submitTranscript opens the panel (above)
          in the same tick — this bubble only ever covers the listening
          phase now, before there's a transcript to show there yet. */}
      {isListening && (
        <div
          style={{
            maxWidth: 260, padding: "8px 12px", borderRadius: 10,
            background: "var(--surface)", boxShadow: "0 4px 12px rgba(0,0,0,0.18)",
            fontSize: 12, lineHeight: 1.4,
            color: interimTranscript ? "var(--on-bg)" : "var(--on-variant)",
            fontStyle: interimTranscript ? "normal" : "italic",
          }}
        >
          {interimTranscript || "Listening…"}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {!isDisabled && (
          <button
            onClick={toggleMuted}
            title={isMuted ? "Unmute spoken responses" : "Mute spoken responses"}
            aria-label={isMuted ? "Unmute spoken responses" : "Mute spoken responses"}
            aria-pressed={isMuted}
            data-testid="voice-mute-toggle"
            suppressHydrationWarning
            style={{
              width: MUTE_TOGGLE_SIZE, height: MUTE_TOGGLE_SIZE, borderRadius: "50%", border: "none",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15,
              cursor: "pointer", background: "var(--surface)", color: "var(--on-variant)",
              boxShadow: "0 2px 8px rgba(0,0,0,0.16)", flexShrink: 0,
            }}
          >
            <i className={`ti ${isMuted ? "ti-volume-off" : "ti-volume"}`} />
          </button>
        )}

        {canType && !isListening && (
          <button
            onClick={() => setIsTypedInputOpen((open) => !open)}
            title={isTypedInputOpen ? "Hide typed command" : "Type a command instead"}
            aria-label={isTypedInputOpen ? "Hide typed command input" : "Type a command instead"}
            aria-pressed={isTypedInputOpen}
            data-testid="voice-fab-type-toggle"
            style={{
              width: MUTE_TOGGLE_SIZE, height: MUTE_TOGGLE_SIZE, borderRadius: "50%", border: "none",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14,
              cursor: "pointer",
              background: isTypedInputOpen ? "var(--primary)" : "var(--surface)",
              color: isTypedInputOpen ? "#fff" : "var(--on-variant)",
              boxShadow: "0 2px 8px rgba(0,0,0,0.16)", flexShrink: 0,
              transition: "background 0.15s, color 0.15s",
            }}
          >
            <i className="ti ti-keyboard" />
          </button>
        )}

        <button
          onClick={isDisabled ? undefined : (isListening ? stopListening : startListening)}
          disabled={isDisabled}
          title={isDisabled ? disabledReason : (isListening ? "Click to stop and send" : "Click to speak a voice command")}
          data-testid="voice-fab"
          style={{
            width: FAB_SIZE, height: FAB_SIZE, borderRadius: "50%", border: "none",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
            cursor: isDisabled || isProcessing ? "not-allowed" : "pointer",
            background: isDisabled ? "var(--bg-low)" : isListening ? "var(--error)" : "var(--primary)",
            color: isDisabled ? "var(--on-variant)" : "#fff",
            opacity: isProcessing ? 0.7 : 1,
            boxShadow: "0 4px 12px rgba(0,0,0,0.18)",
            userSelect: "none",
            transition: "background 0.15s, opacity 0.15s",
          }}
        >
          {isProcessing ? (
            <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />
          ) : (
            <i
              className={`ti ${isDisabled ? "ti-microphone-off" : "ti-microphone"}`}
              style={isListening ? { animation: "clockPulse 1s ease-in-out infinite" } : undefined}
            />
          )}
        </button>
      </div>
    </div>
  );
}
