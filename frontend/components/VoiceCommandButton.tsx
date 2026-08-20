"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useVoiceCommand } from "@/hooks/useVoiceCommand";
import { useVoiceMutePreference } from "@/hooks/useVoiceMutePreference";
import VoiceConversationPanel from "@/components/VoiceConversationPanel";
import FaceVerificationModal from "@/components/FaceVerificationModal";

// One button, one size — no separate idle-orb/expanded-row states any more.
// Clicking it always opens the same VoiceConversationPanel (greeting phase,
// or whatever the active conversation's phase is), which itself already
// offers both a mic button and a "type your answer" text field
// (VoiceInputControls) — so a single launcher covers voice AND typed entry
// without needing its own separate keyboard-toggle icon.
const LAUNCHER_SIZE = 72;

const EDGE_MARGIN = 8;
// The drag-clamp ceiling must match the button's actual footprint — these
// used to be sized for the old wider multi-button hover row, which no
// longer exists (a single LAUNCHER_SIZE button is all that's dragged now).
// Left stale after that redesign, they clamped the drag area tighter than
// the button itself, so the default resting corner was already past the
// ceiling and the button snapped inward the instant a drag began.
const SAFE_W = LAUNCHER_SIZE + EDGE_MARGIN;
const SAFE_H = LAUNCHER_SIZE + EDGE_MARGIN;

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
    submitTranscript, submitFaceProof, conversation, closeConversation,
    isListeningForInterruption, history,
  } = useVoiceCommand(isMuted, isAuthenticated);

  // Opens the same VoiceConversationPanel used for the rest of the exchange
  // (see the "greeting" phase branch below), ahead of any real conversation
  // existing yet — the launcher's only job is opening this, voice vs typed
  // is then whichever the user picks inside VoiceInputControls.
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  const isListening  = status === "listening";
  const isProcessing = status === "processing";

  const [isHovered, setIsHovered] = useState(false);

  // Draggable widget — lets a user physically move it off whatever it's
  // covering (table pagination, wizard footers) instead of just hoping the
  // default corner never collides with page content. Deliberately in-memory
  // only, not persisted — it survives client-side navigation (this component
  // lives in the root layout, which React Router keeps mounted across route
  // changes) but resets to the default corner on an actual page reload, by
  // design.
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

  function handleDragPointerDown(e: React.PointerEvent<HTMLButtonElement>) {
    // Measure the button itself, not the outer container — the container
    // also wraps the hover tooltip when it's visible, which is wider/taller
    // than the button and right-aligned above it. Measuring the container
    // captured the tooltip's top-left corner as the drag origin; the
    // instant a drag started the tooltip unmounted (its render condition
    // includes !isDragging), so the button snapped to align with where the
    // tooltip used to be instead of tracking the mouse.
    const rect = e.currentTarget.getBoundingClientRect();
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
      // The click event that follows this pointerup must not also open the
      // panel — the drag itself was the intended action.
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

  // Every voice response now opens this panel — the recognized transcript
  // while the request is in flight, then the result, whether the intent was
  // conversational or a one-shot. The panel replaces the plain button in
  // place, so it reads as the launcher expanding rather than a separate
  // destination. Never shown while logged out/unsupported: isDisabled
  // already gates whether a conversation could ever have started (see
  // useVoiceCommand's submitTranscript, which checks the same condition
  // before falling back to a toast).
  if (conversation && !isDisabled) {
    return (
      <>
        <VoiceConversationPanel
          transcript={conversation.transcript}
          message={conversation.message}
          phase={conversation.phase}
          conversational={conversation.conversational}
          awaitingInput={conversation.awaitingInput}
          isListening={isListening}
          isProcessing={isProcessing}
          interimTranscript={interimTranscript}
          onStartListening={startListening}
          onStopListening={stopListening}
          onSubmitText={submitTranscript}
          onClose={closeConversation}
          isMuted={isMuted}
          onToggleMute={toggleMuted}
          isListeningForInterruption={isListeningForInterruption}
          history={history}
        />
        {/* Opens on top of the panel above for clock_in/clock_out's "taking
            facial proof" turn (see conversation_clock_in_face.py) — same
            modal the manual ClockWidget/ClockInButton use, so registering/
            capturing looks identical regardless of how the punch started.
            onClose has nowhere useful to fall back to (declining leaves the
            punch mid-dialogue), so it just closes the whole conversation —
            the pending state on the backend expires on its own (120s TTL). */}
        <FaceVerificationModal
          key={conversation.faceProofTurn}
          isOpen={conversation.awaitingFaceProof}
          onCaptured={submitFaceProof}
          onClose={closeConversation}
        />
      </>
    );
  }

  // Launcher click opens the same panel in its "greeting" phase — a chat box
  // with a static hello, quick-action chips, and the mic/typed input
  // controls, open before any real command exists. Submitting from here
  // calls submitTranscript the same as every other entry point, which sets
  // `conversation` and hands rendering back to the branch above for the rest
  // of the exchange.
  //
  // Rendered whenever isAuthenticated (not gated on isDisabled) — typing
  // needs only authentication, not Web Speech API support, so this chat box
  // must still open on non-Chromium browsers (the one place typed commands
  // work at all there); the mic button inside it stays disabled/absent per
  // VoiceInputControls' own isProcessing/isListening handling. On such a
  // browser, submitTranscript's own isDisabled check still routes the
  // *result* to a toast instead of setting `conversation` (see its
  // docstring) — this panel simply stays open afterwards, ready for the
  // next typed command, rather than transitioning to a transcript/result
  // view it can't show there.
  if (isPanelOpen && isAuthenticated) {
    return (
      <VoiceConversationPanel
        transcript=""
        message=""
        phase="greeting"
        conversational={false}
        awaitingInput={false}
        isListening={isListening}
        isProcessing={isProcessing}
        interimTranscript={interimTranscript}
        onStartListening={startListening}
        onStopListening={stopListening}
        onSubmitText={submitTranscript}
        onClose={() => setIsPanelOpen(false)}
        isMuted={isMuted}
        onToggleMute={toggleMuted}
        isListeningForInterruption={false}
        history={history}
      />
    );
  }

  return (
    <div
      onMouseEnter={() => { if (!isDragging) setIsHovered(true); }}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        position: "fixed", zIndex: 1000,
        ...(dragPos
          ? { left: dragPos.x, top: dragPos.y }
          : { right: 4, bottom: 4 }),
        display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8,
      }}
    >
      {/* Hover prompt — bilingual, matches the reference "How can I help
          you?" speech-bubble pattern. Shown only before the panel is ever
          opened; once engaged there's no reason to keep nudging. */}
      {isHovered && !isDragging && !isDisabled && (
        <div
          data-testid="voice-hover-tooltip"
          style={{
            maxWidth: 220, padding: "8px 12px", borderRadius: 10,
            background: "var(--surface)", boxShadow: "0 4px 12px rgba(0,0,0,0.18)",
            fontSize: 12.5, lineHeight: 1.5, color: "var(--on-bg)",
          }}
        >
          <div>How can I help you?</div>
          <div lang="hi" style={{ color: "var(--on-variant)" }}>मैं आपकी कैसे मदद कर सकता हूँ?</div>
        </div>
      )}

      <button
        onClick={() => {
          if (justDraggedRef.current) { justDraggedRef.current = false; return; }
          if (!isAuthenticated) return;
          setIsPanelOpen(true);
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
          width: LAUNCHER_SIZE, height: LAUNCHER_SIZE, borderRadius: "50%", border: "none",
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20,
          cursor: isDragging ? "grabbing" : "pointer",
          touchAction: "none", userSelect: "none", overflow: "visible",
          // No hard solid circle behind the mascot (per direct feedback that
          // looked wrong) — but the character is mostly white/silver, so on
          // a light page background it needs *some* contrast or it
          // disappears entirely. A soft radial glow that fades to fully
          // transparent well before the edge reads as "glow", not "badge".
          background: isDisabled
            ? "var(--bg-low)"
            : "radial-gradient(circle, rgba(37,99,235,0.38) 0%, rgba(37,99,235,0.20) 45%, rgba(37,99,235,0) 72%)",
          color: isDisabled ? "var(--on-variant)" : "#fff",
          boxShadow: isDisabled ? "0 4px 12px rgba(0,0,0,0.18)" : "none",
        }}
      >
        {isDisabled ? (
          // Mic-off, not the mascot, while genuinely unavailable (logged
          // out / unsupported browser) — a friendly bot face here would
          // read as "available", the opposite of what this state means.
          <i className="ti ti-microphone-off" />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src="/bot.png"
            alt=""
            aria-hidden="true"
            // Images are natively draggable by default; without this, the
            // browser's own HTML5 drag-and-drop (dragstart/drag/dragend)
            // hijacks the pointer stream the instant the mouse moves a few
            // pixels, stopping the custom pointermove-based drag above dead
            // after its first event instead of tracking the cursor.
            draggable={false}
            className="voice-bot-float"
            // contain, not cover — bot.png is a transparent PNG with the
            // character centered and padding around it; cover was zooming
            // in tight enough to crop most of the character out. No solid
            // background behind it any more (see above) — drop-shadow
            // instead of a box-shadow gives it depth against the page
            // itself, following the actual alpha shape rather than a box.
            style={{
              width: "100%", height: "100%", objectFit: "contain",
              filter: isDragging ? "drop-shadow(0 8px 16px rgba(0,0,0,0.35))" : "drop-shadow(0 3px 8px rgba(0,0,0,0.25))",
            }}
          />
        )}
      </button>
    </div>
  );
}
