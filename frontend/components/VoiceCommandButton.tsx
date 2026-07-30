"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useVoiceCommand } from "@/hooks/useVoiceCommand";
import { useVoiceMutePreference } from "@/hooks/useVoiceMutePreference";
import VoiceConversationPanel from "@/components/VoiceConversationPanel";

const FAB_SIZE = 56;
const MUTE_TOGGLE_SIZE = 32;
const IDLE_SIZE = 46;

// Dragging only ever moves the idle orb (46px), but it can expand into the
// full mute/keyboard/mic row afterward — reserve room for that wider/taller
// shape so a corner drop never leaves the expanded row spilling off-screen.
const EDGE_MARGIN = 8;
const SAFE_W = 180;
const SAFE_H = 90;

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

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

  // Lets a user type the very first command instead of speaking it — the
  // typed-answer input for mid-conversation follow-ups already exists in
  // VoiceConversationPanel; this is the same idea, just for before any
  // conversation has started. Local UI-only state (not lifted into
  // useVoiceCommand) since nothing outside this component's render needs it.
  const [isTypedInputOpen, setIsTypedInputOpen] = useState(false);
  const [typedValue, setTypedValue] = useState("");

  if (HIDDEN_ROUTES.includes(pathname)) return null;

  const isListening  = status === "listening";
  const isProcessing = status === "processing";

  // Idle state: the FAB rests as a small orb and only expands to the full
  // mic/mute/keyboard row on hover (desktop) or tap (touch — no real hover
  // event, so the orb's own onClick also expands it). Always expanded while
  // actually in use so it can never collapse out from under an active
  // interaction.
  const [isHovered, setIsHovered] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const isBusy = isListening || isProcessing || isTypedInputOpen || !!interimTranscript;
  const showExpanded = isHovered || isBusy;

  // Draggable widget — lets a user physically move it off whatever it's
  // covering (table pagination, wizard footers) instead of just hoping the
  // default corner never collides with page content. Deliberately in-memory
  // only, not persisted — it survives client-side navigation (this component
  // lives in the root layout, which React Router keeps mounted across route
  // changes) but resets to the default corner on an actual page reload, by
  // design. Declared before the outside-click effect below, which reads
  // isDragging.
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragStateRef = useRef<{ startX: number; startY: number; origX: number; origY: number; moved: boolean } | null>(null);
  const justDraggedRef = useRef(false);

  // Re-clamp on resize so a drag from earlier in the session doesn't drift
  // off-screen after resizing the window.
  useEffect(() => {
    function handleResize() {
      setDragPos(prev => prev && {
        x: clamp(prev.x, EDGE_MARGIN, window.innerWidth - SAFE_W),
        y: clamp(prev.y, EDGE_MARGIN, window.innerHeight - SAFE_H),
      });
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Touch devices don't fire mouseleave, so an expanded-by-tap orb would
  // otherwise stay expanded forever — collapse on the next tap/click
  // anywhere outside the widget instead, but never while actually busy or
  // mid-drag (a drag must never trigger a state change that swaps out the
  // element currently holding pointer capture).
  useEffect(() => {
    if (!isHovered || isBusy || isDragging) return;
    function handleOutside(e: MouseEvent | TouchEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsHovered(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("touchstart", handleOutside);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("touchstart", handleOutside);
    };
  }, [isHovered, isBusy, isDragging]);

  function handleDragPointerDown(e: React.PointerEvent<HTMLButtonElement>) {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragStateRef.current = { startX: e.clientX, startY: e.clientY, origX: rect.left, origY: rect.top, moved: false };
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function handleDragPointerMove(e: React.PointerEvent<HTMLButtonElement>) {
    const ds = dragStateRef.current;
    if (!ds) return;
    const dx = e.clientX - ds.startX;
    const dy = e.clientY - ds.startY;
    // Threshold so an ordinary click doesn't register as a drag — a real
    // mouse click alone can easily move 4-5px between press and release,
    // which was previously enough to misfire and save a stray position.
    if (!ds.moved && Math.hypot(dx, dy) > 10) {
      ds.moved = true;
      setIsDragging(true);
    }
    if (ds.moved) {
      setDragPos({
        x: clamp(ds.origX + dx, EDGE_MARGIN, window.innerWidth - SAFE_W),
        y: clamp(ds.origY + dy, EDGE_MARGIN, window.innerHeight - SAFE_H),
      });
    }
  }

  function handleDragPointerUp(e: React.PointerEvent<HTMLButtonElement>) {
    const ds = dragStateRef.current;
    if (ds?.moved) {
      // The click event that follows this pointerup must not also expand
      // the orb — the drag itself was the intended action.
      justDraggedRef.current = true;
      const x = clamp(ds.origX + (e.clientX - ds.startX), EDGE_MARGIN, window.innerWidth - SAFE_W);
      const y = clamp(ds.origY + (e.clientY - ds.startY), EDGE_MARGIN, window.innerHeight - SAFE_H);
      setDragPos({ x, y });
    }
    dragStateRef.current = null;
    setIsDragging(false);
  }

  if (HIDDEN_ROUTES.includes(pathname)) return null;

  const disabledReason = !isAuthenticated
    ? "Log in to use voice commands"
    : "Voice commands need a Chromium-based browser (Chrome, Edge) — the Web Speech API isn't available here.";

  // Typing doesn't need the Web Speech API the mic button requires — only
  // authentication does (the same server-side gate /api/voice/parse/
  // enforces regardless). Gating on isAuthenticated alone, not isDisabled,
  // means this also becomes the working fallback on non-Chromium browsers.
  const canType = isAuthenticated;

  function handleTypedSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = typedValue.trim();
    if (!trimmed || isProcessing) return;
    setTypedValue("");
    setIsTypedInputOpen(false);
    // Same submitTranscript() the recognized-speech path and the mid-
    // conversation typed-answer input both call — one /api/voice/parse/
    // flow and one response-handling path for every submission, spoken or
    // typed, first turn or follow-up.
    submitTranscript(trimmed);
  }

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
        onClose={() => { setIsHovered(false); closeConversation(); }}
        isMuted={isMuted}
        onToggleMute={toggleMuted}
      />
    );
  }

  return (
    <div
      ref={containerRef}
      onMouseEnter={() => { if (!isDragging) setIsHovered(true); }}
      onMouseLeave={() => { if (!isBusy && !isDragging) setIsHovered(false); }}
      style={{
        position: "fixed", zIndex: 1000,
        ...(dragPos
          ? { left: dragPos.x, top: dragPos.y }
          : { right: 4, bottom: 4 }),
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

      {/* Typed-first-command row — only reachable via the keyboard toggle
          below, and hidden the moment listening starts so it never fights
          the interim-transcript bubble above for the same space. */}
      {isTypedInputOpen && !isListening && (
        <form
          onSubmit={handleTypedSubmit}
          style={{ display: "flex", gap: 6, width: 260, maxWidth: "calc(100vw - 40px)" }}
        >
          <input
            type="text"
            autoFocus
            value={typedValue}
            onChange={(e) => setTypedValue(e.target.value)}
            placeholder="Type a command…"
            disabled={isProcessing}
            data-testid="voice-fab-typed-input"
            style={{
              flex: 1, height: 38, borderRadius: 10, border: "1.5px solid var(--outline-v)",
              background: "var(--surface)", color: "var(--on-bg)", fontSize: 13,
              padding: "0 12px", outline: "none", minWidth: 0,
              boxShadow: "0 4px 12px rgba(0,0,0,0.18)",
            }}
          />
          <button
            type="submit"
            disabled={!typedValue.trim() || isProcessing}
            aria-label="Send typed command"
            title="Send"
            data-testid="voice-fab-typed-send"
            style={{
              width: 38, height: 38, borderRadius: 10, border: "none",
              background: "var(--primary)", color: "#fff",
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: !typedValue.trim() || isProcessing ? "not-allowed" : "pointer",
              opacity: !typedValue.trim() || isProcessing ? 0.7 : 1,
              flexShrink: 0,
            }}
          >
            <i className="ti ti-send" style={{ fontSize: 15 }} />
          </button>
        </form>
      )}

      {!showExpanded ? (
        // Idle resting state — a small orb, not the full row, so the widget
        // stops competing with page content (table pagination, wizard
        // footers) for the same corner. Hover/tap expands it below; press
        // and drag physically moves it (position persists across reloads).
        <button
          onMouseEnter={() => { if (!isDragging) setIsHovered(true); }}
          onClick={() => {
            if (justDraggedRef.current) { justDraggedRef.current = false; return; }
            setIsHovered(true);
          }}
          onPointerDown={handleDragPointerDown}
          onPointerMove={handleDragPointerMove}
          onPointerUp={handleDragPointerUp}
          onPointerCancel={handleDragPointerUp}
          aria-label={isDisabled ? disabledReason : "Open voice assistant — press and drag to move"}
          title={isDisabled ? disabledReason : "Voice assistant — drag to move"}
          data-testid="voice-fab-idle"
          className={!isDisabled && !isDragging ? "voice-fab-idle-pulse" : undefined}
          style={{
            width: IDLE_SIZE, height: IDLE_SIZE, borderRadius: "50%", border: "none",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
            cursor: isDragging ? "grabbing" : "pointer",
            touchAction: "none", userSelect: "none",
            background: isDisabled ? "var(--bg-low)" : "var(--primary)",
            color: isDisabled ? "var(--on-variant)" : "#fff",
            boxShadow: isDragging ? "0 8px 20px rgba(0,0,0,0.28)" : "0 4px 12px rgba(0,0,0,0.18)",
          }}
        >
          <i className={`ti ${isDisabled ? "ti-microphone-off" : "ti-microphone"}`} />
        </button>
      ) : (
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
          onClick={() => {
            if (justDraggedRef.current) { justDraggedRef.current = false; return; }
            if (isDisabled) return;
            if (isListening) stopListening();
            else { setIsTypedInputOpen(false); startListening(); }
          }}
          onPointerDown={isDisabled ? undefined : handleDragPointerDown}
          onPointerMove={isDisabled ? undefined : handleDragPointerMove}
          onPointerUp={isDisabled ? undefined : handleDragPointerUp}
          onPointerCancel={isDisabled ? undefined : handleDragPointerUp}
          disabled={isDisabled}
          title={isDisabled ? disabledReason : (isListening ? "Click to stop and send — press and drag to move" : "Click to speak a voice command — press and drag to move")}
          data-testid="voice-fab"
          style={{
            width: FAB_SIZE, height: FAB_SIZE, borderRadius: "50%", border: "none",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
            cursor: isDisabled || isProcessing ? "not-allowed" : isDragging ? "grabbing" : "pointer",
            touchAction: "none",
            background: isDisabled ? "var(--bg-low)" : isListening ? "var(--error)" : "var(--primary)",
            color: isDisabled ? "var(--on-variant)" : "#fff",
            opacity: isProcessing ? 0.7 : 1,
            boxShadow: isDragging ? "0 8px 20px rgba(0,0,0,0.28)" : "0 4px 12px rgba(0,0,0,0.18)",
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
      )}
    </div>
  );
}
