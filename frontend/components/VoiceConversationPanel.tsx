"use client";

import { useEffect, useRef } from "react";
import type { VoiceHistoryEntry, VoicePanelPhase, VoiceResultStatus } from "@/hooks/useVoiceCommand";
import VoiceInputControls from "@/components/VoiceInputControls";

// Static placeholder shown only in the "greeting" phase, before any command
// has been typed or spoken yet — never sent through speak() (see
// useVoiceCommand.ts), so it never delays the user actually giving a
// command by narrating itself first. Naming coincidence only: unrelated to
// the backend's "greeting" voice intent (registry/intents_en.yaml, matched
// when the user actually says "hi"/"hello"/"good morning" etc.) — this
// string is pure frontend UI and never reaches /api/voice/parse/.
const GREETING_MESSAGE = "Hi, how can I help you?";

// One tap submits the phrase exactly like a typed command (onSubmitText),
// so it goes through the real /voice/parse/ pipeline — not a shortcut, not
// a different code path. Every phrase here is copied verbatim from
// backend/apps/voice_commands/registry/intents_en.yaml so a tap is
// guaranteed to match, and every one of these intents has
// required_permission: null — available to literally every authenticated
// employee, so the chips never need per-user permission filtering.
const QUICK_ACTIONS: { label: string; phrase: string; icon: string }[] = [
  { label: "Clock In",           phrase: "clock in",                   icon: "ti-login-2" },
  { label: "Clock Out",          phrase: "clock out",                  icon: "ti-logout-2" },
  { label: "Leave Balance",      phrase: "check my leave balance",     icon: "ti-calendar-stats" },
  { label: "Apply for Leave",    phrase: "apply for leave",            icon: "ti-calendar-plus" },
  { label: "My Attendance",      phrase: "show my attendance summary", icon: "ti-clipboard-list" },
];

const BOT_AVATAR_SRC = "/bot.png";

function BotAvatar({ size = 24 }: { size?: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={BOT_AVATAR_SRC}
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      // contain, not cover — bot.png is a transparent PNG with the
      // character centered and padding around it; cover crops in tight
      // enough to lose most of the character at small sizes.
      style={{ width: size, height: size, borderRadius: "50%", flexShrink: 0, objectFit: "contain", background: "var(--bg-low)" }}
    />
  );
}

function ResultIcon({ resultStatus }: { resultStatus: VoiceResultStatus }) {
  return (
    <i
      className={`ti ${resultStatus === "error" ? "ti-alert-circle" : "ti-circle-check"}`}
      style={{ fontSize: 12, color: resultStatus === "error" ? "var(--error)" : "var(--success)" }}
    />
  );
}

// Past completed exchanges, oldest first — each rendered as a right-aligned
// "you said" bubble followed by a left-aligned assistant bubble, so a
// returning user scrolls up through something that actually reads as a
// conversation instead of only ever seeing the latest turn. No avatar per
// bubble — bot.png is a detailed, glossy render that reads as a mismatched
// sticker at the ~20px an inline per-message icon would need; alignment +
// color alone already disambiguates the two sides of a 2-party chat, the
// same way most minimal chat UIs work. The one appearance of the mascot in
// this panel is the header (full-size, where its detail actually holds up).
function HistoryList({ history }: { history: VoiceHistoryEntry[] }) {
  if (history.length === 0) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {history.map(entry => (
        <div key={entry.id} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <div
              style={{
                maxWidth: "80%", padding: "6px 10px", borderRadius: "12px 12px 2px 12px",
                background: "var(--primary)", color: "#fff", fontSize: 12.5, lineHeight: 1.4,
              }}
            >
              {entry.transcript}
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <div
              style={{
                maxWidth: "82%", padding: "6px 10px", borderRadius: "12px 12px 12px 2px",
                background: "var(--bg-low)", color: "var(--on-bg)", fontSize: 12.5, lineHeight: 1.4,
                display: "flex", alignItems: "flex-start", gap: 6,
              }}
            >
              <span>{entry.message}</span>
              <span style={{ marginTop: 2 }}><ResultIcon resultStatus={entry.resultStatus} /></span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function QuickActionChips({ onPick }: { onPick: (phrase: string) => void }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {QUICK_ACTIONS.map(action => (
        <button
          key={action.phrase}
          onClick={() => onPick(action.phrase)}
          data-testid={`voice-quick-action-${action.phrase.replace(/\s+/g, "-")}`}
          style={{
            display: "flex", alignItems: "center", gap: 5,
            padding: "6px 10px", borderRadius: 16, border: "1px solid var(--outline-v)",
            background: "var(--surface)", color: "var(--on-bg)", fontSize: 11.5, fontWeight: 500,
            cursor: "pointer", whiteSpace: "nowrap",
          }}
        >
          <i className={`ti ${action.icon}`} style={{ fontSize: 13, color: "var(--primary)" }} />
          {action.label}
        </button>
      ))}
    </div>
  );
}

interface VoiceConversationPanelProps {
  transcript: string;
  message: string;
  phase: VoicePanelPhase;
  isListening: boolean;
  isProcessing: boolean;
  interimTranscript: string;
  onStartListening: () => void;
  onStopListening: () => void;
  onSubmitText: (text: string) => void;
  onClose: () => void;
  isMuted: boolean;
  onToggleMute: () => void;
  // True while a barge-in VAD tap is actually open (TTS is speaking and mic
  // permission for the tap succeeded) — surfaced so the mic being live
  // during every spoken response is visible, not silent (see
  // useVoiceCommand.ts's startVadTap).
  isListeningForInterruption: boolean;
  // Past completed exchanges (see useVoiceCommand's VoiceHistoryEntry) —
  // rendered above whatever the current phase shows, so this reads as one
  // continuous chat rather than a single-turn popup. Empty on a fresh
  // session/after a reload; not cleared just because the panel closes.
  history: VoiceHistoryEntry[];
}

const PANEL_WIDTH = 300;
const MAX_BODY_HEIGHT = 360;

// Anchored where the mic FAB normally sits — VoiceCommandButton swaps the
// plain button out for this panel for every voice response now (not just
// conversational ones), so this reads as the mic icon expanding in place,
// not a separate destination.
export default function VoiceConversationPanel({
  transcript, message, phase,
  isListening, isProcessing, interimTranscript,
  onStartListening, onStopListening, onSubmitText, onClose,
  isMuted, onToggleMute, isListeningForInterruption, history,
}: VoiceConversationPanelProps) {
  const bodyRef = useRef<HTMLDivElement>(null);

  // Keep the latest turn in view as history/phase/message change — a chat
  // transcript that silently leaves you scrolled up on the previous turn
  // while a new one lands below the fold defeats the point of showing
  // history at all.
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [history.length, phase, message, transcript]);

  return (
    <div
      data-testid="voice-panel"
      style={{
        position: "fixed", right: 20, bottom: 20, zIndex: 1000,
        width: PANEL_WIDTH, maxWidth: "calc(100vw - 40px)",
        display: "flex", flexDirection: "column",
        background: "var(--surface)", borderRadius: 14,
        boxShadow: "0 8px 28px rgba(0,0,0,0.22)", overflow: "hidden",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px 8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <BotAvatar size={20} />
          <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--on-variant)" }}>
            Voice Assistant
          </span>
          {isListeningForInterruption && (
            <span
              data-testid="voice-panel-barge-in-indicator"
              title="Listening for interruption — speak to cut in"
              aria-label="Listening for interruption — speak to cut in"
              style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                fontSize: 10, color: "var(--primary)",
              }}
            >
              <i
                className="ti ti-microphone"
                style={{ fontSize: 11, animation: "voiceBargeInPulse 1.2s ease-in-out infinite" }}
              />
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
          <button
            onClick={onToggleMute}
            title={isMuted ? "Unmute spoken responses" : "Mute spoken responses"}
            aria-label={isMuted ? "Unmute spoken responses" : "Mute spoken responses"}
            aria-pressed={isMuted}
            data-testid="voice-panel-mute-toggle"
            suppressHydrationWarning
            style={{
              width: 22, height: 22, borderRadius: 6, border: "none", background: "transparent",
              color: "var(--on-variant)", cursor: "pointer", display: "flex",
              alignItems: "center", justifyContent: "center", fontSize: 13, padding: 0,
            }}
          >
            <i className={`ti ${isMuted ? "ti-volume-off" : "ti-volume"}`} />
          </button>
          <button
            onClick={onClose}
            aria-label="Close voice assistant"
            title="Close"
            data-testid="voice-panel-close"
            style={{
              width: 22, height: 22, borderRadius: 6, border: "none", background: "transparent",
              color: "var(--on-variant)", cursor: "pointer", display: "flex",
              alignItems: "center", justifyContent: "center", fontSize: 13, padding: 0,
            }}
          >
            <i className="ti ti-x" />
          </button>
        </div>
      </div>

      {/* Scrollable body: past history (if any) + whatever the current phase shows */}
      <div
        ref={bodyRef}
        style={{
          display: "flex", flexDirection: "column", gap: 12,
          padding: "4px 14px 14px", overflowY: "auto", maxHeight: MAX_BODY_HEIGHT,
        }}
      >
        <HistoryList history={history} />

        {phase === "greeting" ? (
          <>
            {/* Opened via the keyboard toggle, before anything has been typed
                or spoken yet — same message styling as a real assistant
                response (voice-panel-message below) so it reads as part of
                the same conversation, not a separate splash screen. */}
            {history.length === 0 && (
              <div data-testid="voice-panel-greeting" style={{ fontSize: 13, lineHeight: 1.5, color: "var(--on-bg)" }}>
                {GREETING_MESSAGE}
              </div>
            )}
            <QuickActionChips onPick={onSubmitText} />
            <VoiceInputControls
              isListening={isListening}
              isProcessing={isProcessing}
              interimTranscript={interimTranscript}
              onStartListening={onStartListening}
              onStopListening={onStopListening}
              onSubmitText={onSubmitText}
            />
          </>
        ) : phase === "transcript" ? (
          <>
            {/* What was recognized, shown while the request is in flight —
                every voice response starts here now, not just conversational
                ones (see useVoiceCommand's submitTranscript). */}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <div
                data-testid="voice-panel-transcript"
                style={{
                  maxWidth: "80%", padding: "6px 10px", borderRadius: "12px 12px 2px 12px",
                  background: "var(--primary)", color: "#fff", fontSize: 12.5, lineHeight: 1.4, fontStyle: "italic",
                }}
              >
                “{transcript}”
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2" style={{ fontSize: 15, animation: "spin 1s linear infinite" }} />
              Processing…
            </div>
          </>
        ) : (
          // phase === "result": the outcome is already the last entry in
          // `history` (useVoiceCommand appends at the exact moment it sets
          // this phase) — HistoryList above already rendered it, bubble,
          // bot avatar, checkmark/error icon and all. Input controls show
          // here regardless of conversational/awaitingInput — a one-shot
          // result auto-closes after a delay (IMMEDIATE_RESULT_AUTO_CLOSE_MS
          // in useVoiceCommand.ts), and without this the user couldn't type
          // a follow-up command until that timer fired and reopened the
          // greeting screen. Submitting here calls submitTranscript, which
          // already clears the pending auto-close timer at its start, so
          // there's no race between a fresh request and the old timer.
          <VoiceInputControls
            isListening={isListening}
            isProcessing={isProcessing}
            interimTranscript={interimTranscript}
            onStartListening={onStartListening}
            onStopListening={onStopListening}
            onSubmitText={onSubmitText}
          />
        )}
      </div>
    </div>
  );
}
