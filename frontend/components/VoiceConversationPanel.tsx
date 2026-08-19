"use client";

import type { VoicePanelPhase, VoiceResultStatus } from "@/hooks/useVoiceCommand";
import VoiceInputControls from "@/components/VoiceInputControls";

// Static placeholder shown only in the "greeting" phase, before any command
// has been typed or spoken yet — never sent through speak() (see
// useVoiceCommand.ts), so it never delays the user actually giving a
// command by narrating itself first. Naming coincidence only: unrelated to
// the backend's "greeting" voice intent (registry/intents_en.yaml, matched
// when the user actually says "hi"/"hello"/"good morning" etc.) — this
// string is pure frontend UI and never reaches /api/voice/parse/.
const GREETING_MESSAGE = "Hi, how can I help you?";

interface VoiceConversationPanelProps {
  transcript: string;
  message: string;
  phase: VoicePanelPhase;
  conversational: boolean;
  awaitingInput: boolean;
  resultStatus: VoiceResultStatus | null;
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
}

const PANEL_WIDTH = 300;

// Anchored where the mic FAB normally sits — VoiceCommandButton swaps the
// plain button out for this panel for every voice response now (not just
// conversational ones), so this reads as the mic icon expanding in place,
// not a separate destination.
export default function VoiceConversationPanel({
  transcript, message, phase, conversational, awaitingInput, resultStatus,
  isListening, isProcessing, interimTranscript,
  onStartListening, onStopListening, onSubmitText, onClose,
  isMuted, onToggleMute, isListeningForInterruption,
}: VoiceConversationPanelProps) {
  return (
    <div
      data-testid="voice-panel"
      style={{
        position: "fixed", right: 20, bottom: 20, zIndex: 1000,
        width: PANEL_WIDTH, maxWidth: "calc(100vw - 40px)",
        display: "flex", flexDirection: "column", gap: 10,
        background: "var(--surface)", borderRadius: 14, padding: 14,
        boxShadow: "0 8px 28px rgba(0,0,0,0.22)",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
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

      {phase === "greeting" ? (
        <>
          {/* Opened via the keyboard toggle, before anything has been typed
              or spoken yet — same message styling as a real assistant
              response (voice-panel-message below) so it reads as part of
              the same conversation, not a separate splash screen. */}
          <div data-testid="voice-panel-greeting" style={{ fontSize: 13, lineHeight: 1.5, color: "var(--on-bg)" }}>
            {GREETING_MESSAGE}
          </div>
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
          <div
            data-testid="voice-panel-transcript"
            style={{ fontSize: 13, lineHeight: 1.5, color: "var(--on-variant)", fontStyle: "italic" }}
          >
            “{transcript}”
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2" style={{ fontSize: 15, animation: "spin 1s linear infinite" }} />
            Processing…
          </div>
        </>
      ) : conversational ? (
        <>
          {/* Multi-turn dialogue (apply_leave today) — unchanged from before:
              plain message, mic/typed-answer controls while a follow-up
              question is pending. */}
          <div data-testid="voice-panel-message" style={{ fontSize: 13, lineHeight: 1.5, color: "var(--on-bg)" }}>
            {message}
          </div>

          {awaitingInput && (
            <VoiceInputControls
              isListening={isListening}
              isProcessing={isProcessing}
              interimTranscript={interimTranscript}
              onStartListening={onStartListening}
              onStopListening={onStopListening}
              onSubmitText={onSubmitText}
            />
          )}
        </>
      ) : (
        // Immediate-action intent (or no-match) — the whole exchange was one
        // shot, so the result is the last thing shown before the panel
        // auto-closes itself (useVoiceCommand's IMMEDIATE_RESULT_AUTO_CLOSE_MS).
        <div data-testid="voice-panel-result" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <i
            className={`ti ${resultStatus === "error" ? "ti-alert-circle" : "ti-circle-check"}`}
            style={{
              fontSize: 20, flexShrink: 0,
              color: resultStatus === "error" ? "var(--error)" : "var(--success)",
              animation: resultStatus === "error" ? undefined : "voiceCheckPop 0.35s ease-out",
            }}
          />
          <span style={{ fontSize: 13, lineHeight: 1.5, color: "var(--on-bg)" }}>{message}</span>
        </div>
      )}
    </div>
  );
}
