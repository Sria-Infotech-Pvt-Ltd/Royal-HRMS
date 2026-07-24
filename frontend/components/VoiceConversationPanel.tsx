"use client";

import { useState } from "react";
import type { VoicePanelPhase, VoiceResultStatus } from "@/hooks/useVoiceCommand";

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
  isMuted, onToggleMute,
}: VoiceConversationPanelProps) {
  const [typedValue, setTypedValue] = useState("");

  function handleTextSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = typedValue.trim();
    if (!trimmed || isListening || isProcessing) return;
    onSubmitText(trimmed);
    setTypedValue("");
  }

  const micLabel = isListening
    ? (interimTranscript || "Listening…")
    : isProcessing
    ? "Processing…"
    : "Tap to speak";

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
        <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--on-variant)" }}>
          Voice Assistant
        </span>
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

      {phase === "transcript" ? (
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
            <>
              {/* Primary: voice */}
              <button
                onClick={isProcessing ? undefined : (isListening ? onStopListening : onStartListening)}
                disabled={isProcessing}
                data-testid="voice-panel-mic"
                style={{
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                  height: 48, borderRadius: 10, border: "none",
                  background: isListening ? "var(--error)" : "var(--primary)",
                  color: "#fff", fontSize: 13, fontWeight: 500,
                  cursor: isProcessing ? "not-allowed" : "pointer",
                  opacity: isProcessing ? 0.7 : 1,
                  transition: "background 0.15s, opacity 0.15s",
                }}
              >
                <i
                  className={`ti ${isProcessing ? "ti-loader-2" : "ti-microphone"}`}
                  style={{
                    fontSize: 18,
                    animation: isProcessing ? "spin 1s linear infinite" : isListening ? "clockPulse 1s ease-in-out infinite" : undefined,
                  }}
                />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {micLabel}
                </span>
              </button>

              {/* Secondary: type an answer */}
              <form onSubmit={handleTextSubmit} style={{ display: "flex", gap: 6 }}>
                <input
                  type="text"
                  value={typedValue}
                  onChange={(e) => setTypedValue(e.target.value)}
                  placeholder="Or type your answer…"
                  disabled={isListening || isProcessing}
                  data-testid="voice-panel-input"
                  style={{
                    flex: 1, height: 34, borderRadius: 8, border: "1.5px solid var(--outline-v)",
                    background: "var(--bg)", color: "var(--on-bg)", fontSize: 12,
                    padding: "0 10px", outline: "none", minWidth: 0,
                  }}
                />
                <button
                  type="submit"
                  disabled={!typedValue.trim() || isListening || isProcessing}
                  aria-label="Send"
                  data-testid="voice-panel-send"
                  style={{
                    width: 34, height: 34, borderRadius: 8, border: "none",
                    background: "var(--bg-low)", color: "var(--on-variant)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    cursor: !typedValue.trim() || isListening || isProcessing ? "not-allowed" : "pointer",
                    flexShrink: 0,
                  }}
                >
                  <i className="ti ti-send" style={{ fontSize: 14 }} />
                </button>
              </form>
            </>
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
