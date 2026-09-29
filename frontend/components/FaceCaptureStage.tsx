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
export default function FaceCaptureStage({ videoRef, canvasRef, phase }: FaceCaptureStageProps) {
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
      {INSTRUCTION[phase] && (
        <div
          className="absolute bottom-0 left-0 right-0 text-center text-white text-xs py-2 px-3"
          style={{ background: "rgba(0,0,0,0.6)" }}
        >
          {INSTRUCTION[phase]}
        </div>
      )}
    </div>
  );
}
