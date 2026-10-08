"use client";

import type { RefObject } from "react";

interface FaceCaptureStageProps {
  videoRef:  RefObject<HTMLVideoElement | null>;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  // Deliberately a plain string, not a specific hook's phase union — this
  // component is shared by every face-capture flow (registration enrollment,
  // clock-in verification, ...), each with its own extra phases layered on
  // top of the common "detecting"/"liveness_checking" pair used below.
  phase: string;
  /** Live framing/lighting guidance ("Move closer", an auto-retry notice, ...). Overrides the default line while framing. */
  hint?: string | null;
  /** Which liveness signals were already seen — turns "blink AND turn" into "now turn your head". */
  progress?: { blink: boolean; turn: boolean } | null;
}

const INSTRUCTION: Partial<Record<string, string>> = {
  detecting:         "Center your face in the frame",
  liveness_checking: "Please blink naturally AND turn your head slightly",
  // Liveness already passed at this point — the instruction shifts from
  // "prove you're live" to "stay put while we get a clean capture". Shared
  // by every caller's multi-frame sampling pass, registration and
  // punch-time verification alike (useFaceLivenessCapture's framesToCapture).
  capturing_multi:   "Hold still — capturing a clear frame",
};

// The <video>/<canvas> pair here is mounted for the whole lifetime of the
// modal that uses it (see FaceRegistrationModal / FaceVerificationModal) so
// their refs exist before the very first getUserMedia call resolves — this
// component just controls what's shown over them once the stream is live.
function instructionFor(phase: string, hint?: string | null, progress?: { blink: boolean; turn: boolean } | null): string | undefined {
  if (phase === "liveness_checking" && progress) {
    if (progress.blink && !progress.turn) return "Blink \u2713 \u2014 now turn your head slightly";
    if (progress.turn && !progress.blink) return "Head turn \u2713 \u2014 now blink naturally";
  }
  if (phase === "detecting" && hint) return hint;
  return INSTRUCTION[phase];
}

export default function FaceCaptureStage({ videoRef, canvasRef, phase, hint, progress }: FaceCaptureStageProps) {
  const instruction = instructionFor(phase, hint, progress);
  return (
    <div
      className="relative rounded-2xl overflow-hidden mx-auto"
      style={{ width: 320, height: 240, background: "#111" }}
    >
      {/* Mirrored (scaleX(-1)) on both layers together so the overlay box stays aligned with the visual preview. */}
      <video
        ref={videoRef}
        muted
        playsInline
        className="w-full h-full object-cover"
        style={{ transform: "scaleX(-1)" }}
      />
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full pointer-events-none"
        style={{ transform: "scaleX(-1)" }}
      />
      {instruction && (
        <div
          className="absolute bottom-0 left-0 right-0 text-center text-white text-xs py-2 px-3"
          style={{ background: "rgba(0,0,0,0.6)" }}
        >
          {instruction}
        </div>
      )}
    </div>
  );
}
