"use client";

import { useState } from "react";

interface VoiceInputControlsProps {
  isListening: boolean;
  isProcessing: boolean;
  interimTranscript: string;
  onStartListening: () => void;
  onStopListening: () => void;
  onSubmitText: (text: string) => void;
}

// Shared mic + typed-answer controls — used both mid-conversation (awaiting
// a follow-up slot answer) and in the pre-conversation greeting chat box
// VoiceCommandButton opens via the keyboard toggle, so both entry points
// read as the same input surface rather than two differently-built widgets.
export default function VoiceInputControls({
  isListening, isProcessing, interimTranscript,
  onStartListening, onStopListening, onSubmitText,
}: VoiceInputControlsProps) {
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
  );
}
