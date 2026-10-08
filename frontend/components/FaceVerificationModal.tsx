"use client";

// Clock-in identity check for employees with an approved face registration.
// Only captures a live, liveness-passed face descriptor and hands it back
// via onCaptured — the actual punch call (and any "verification failed"
// error from the backend) is owned by whoever renders this modal
// (useClockWidget.ts / ClockInButton.tsx), same as the punch API call itself.
import { useEffect } from "react";
import { createPortal } from "react-dom";
import { useFaceLivenessCapture } from "@/hooks/useFaceLivenessCapture";
import FaceStatusPanel from "@/components/FaceStatusPanel";
import FaceCaptureStage from "@/components/FaceCaptureStage";
import { FACE_FLOW_V2 } from "@/lib/faceApi/flowConfig";

interface FaceVerificationModalProps {
  isOpen:     boolean;
  /** livenessScore/captureSessionId are forwarded straight from
   *  useFaceLivenessCapture — the caller passes them on to the punch API's
   *  liveness_score/capture_session_id fields, which FaceVerificationService's
   *  anti-replay check (services_face_antispoofing.py) needs. */
  onCaptured: (embedding: number[], livenessScore: number, captureSessionId: string) => void;
  onClose:    () => void;
}

// A single quality-gated frame carries enough per-capture noise (motion
// blur, momentary exposure shift, compression artifacts) that its distance
// to the registered reference can drift by several hundredths either way —
// margin that matters when a genuine self-match can itself land as high as
// the mid-0.5s. Averaging a few frames here (fewer than registration's 4,
// since clock-in/out happens far more often and needs to stay reasonably
// quick) cuts that per-capture noise down without adding registration's
// full multi-second capture time to every punch. See the false-accept
// investigation that motivated this in useFaceLivenessCapture.ts's
// framesToCapture docstring.
const VERIFICATION_FRAMES_TO_CAPTURE = 3;

export default function FaceVerificationModal({ isOpen, onCaptured, onClose }: FaceVerificationModalProps) {
  const { phase, errorMessage, liveHint, lowLight, livenessProgress, modelProgress, videoRef, canvasRef, start, retry, stop } = useFaceLivenessCapture({
    // Release the camera the instant we have a descriptor — don't wait for the
    // parent to close the modal. The parent flips isOpen straight to false
    // once it has the embedding, which never re-runs the isOpen effect below
    // (false → the "if (isOpen) start()" branch just doesn't fire), so without
    // this the stream from every capture stayed open and the next clock-in
    // opened a second one on top of it, never releasing either.
    onCaptured: (descriptor, livenessScore, captureSessionId) => {
      stop();
      onCaptured(descriptor, livenessScore, captureSessionId);
    },
    // Same CLAHE lighting normalization and per-frame quality gate
    // (lib/faceApi/qualityGate.ts) as registration — the live capture being
    // matched against a stored reference should be extracted the same way
    // the reference itself was, not from a lower-quality raw frame.
    framesToCapture: VERIFICATION_FRAMES_TO_CAPTURE,
    normalizeLighting: true,
  });

  function handleClose() {
    stop(); // always release the camera, whatever phase we're in
    onClose();
  }

  useEffect(() => {
    if (isOpen) start();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- start() is stable; only isOpen should re-trigger this
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleClose is stable enough for an Escape listener
  }, [isOpen]);

  if (!isOpen) return null;

  const showCameraPreview = phase === "detecting" || phase === "liveness_checking" || phase === "capturing_multi";
  // The screen itself is the light. A phone/laptop display is a soft frontal light source, so while
  // the camera is live the dark backdrop fades to white (gradually - see the transition below - so the
  // camera's auto-exposure follows smoothly instead of jumping) and fades back when capture ends or
  // the modal closes. Browsers cannot raise the device's real brightness, hence the tip when dim.
  const screenLight = FACE_FLOW_V2 && showCameraPreview;
  const fillLight = screenLight && lowLight;

  const overlay = (
    <div
      className="fixed inset-0 flex items-center justify-center p-6"
      style={{
        background: screenLight ? "#ffffff" : "rgba(0,0,0,0.55)",
        zIndex: 9999,
        transition: screenLight ? "background 1.6s ease-in" : "background 0.4s ease-out",
      }}
      onClick={handleClose}
    >
      <div
        className="relative flex flex-col rounded-2xl overflow-hidden shadow-2xl"
        style={{ background: "#fff", width: "min(440px, 92vw)", maxHeight: "88vh" }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 flex-shrink-0" style={{ background: "var(--primary)" }}>
          <div className="flex items-center gap-2.5">
            <i className="ti ti-face-id text-white text-[18px]" />
            <p className="text-[14px] font-semibold text-white leading-tight">Verify Your Identity</p>
          </div>
          <button
            onClick={handleClose}
            suppressHydrationWarning
            className="w-8 h-8 flex items-center justify-center rounded-lg text-white/80 hover:bg-white/15 transition-colors"
          >
            <i className="ti ti-x text-[18px]" />
          </button>
        </div>

        <div className="p-6" style={{ minHeight: 260, overflowY: "auto" }}>
          <div style={{ display: showCameraPreview ? "block" : "none" }}>
            <FaceCaptureStage videoRef={videoRef} canvasRef={canvasRef} phase={phase} hint={liveHint} progress={livenessProgress} />
            {fillLight && (
              <p className="text-center text-[12px] mt-3" style={{ color: "#475569" }}>
                Low light detected — your screen is now acting as a light. Raising your screen brightness helps.
              </p>
            )}
          </div>

          {(phase === "idle" || phase === "loading_models") && (
            <FaceStatusPanel
              icon="ti-loader-2" iconColor="var(--primary)" iconBg="rgba(30,78,140,0.08)" spinning
              title="Preparing face verification" message="Downloading face models (first time only)…" progress={modelProgress}
            />
          )}

          {phase === "requesting_camera" && (
            <FaceStatusPanel
              icon="ti-camera" iconColor="var(--primary)" iconBg="rgba(30,78,140,0.08)" spinning
              title="Requesting camera access" message="Please allow camera access in the browser prompt to clock in."
            />
          )}

          {phase === "camera_denied" && (
            <FaceStatusPanel
              icon="ti-camera-off" iconColor="var(--error)" iconBg="rgba(239,68,68,0.08)"
              title="Camera access denied"
              message="Your account requires face verification to clock in/out. Allow camera access for this site in your browser's settings, then try again."
              action={{ label: "Try Again", onClick: retry }}
              secondaryAction={{ label: "Cancel", onClick: handleClose }}
            />
          )}

          {phase === "liveness_failed" && (
            <FaceStatusPanel
              icon="ti-alert-triangle" iconColor="#b45309" iconBg="rgba(234,179,8,0.12)"
              title="Couldn't confirm you're live"
              message="We didn't detect both a natural blink and a slight head turn in time. Make sure you're well-lit and centered, then try again."
              action={{ label: "Try Again", onClick: retry }}
              secondaryAction={{ label: "Cancel", onClick: handleClose }}
            />
          )}

          {phase === "quality_failed" && (
            <FaceStatusPanel
              icon="ti-alert-triangle" iconColor="#b45309" iconBg="rgba(234,179,8,0.12)"
              title="Capture wasn't clear enough"
              message={
                errorMessage
                ?? "We couldn't get a reliably clear capture to verify against your registered face. Try better lighting and hold steady."
              }
              action={{ label: "Try Again", onClick: retry }}
              secondaryAction={{ label: "Cancel", onClick: handleClose }}
            />
          )}

          {phase === "error" && (
            <FaceStatusPanel
              icon="ti-alert-circle" iconColor="var(--error)" iconBg="rgba(239,68,68,0.08)"
              title="Something went wrong"
              message={errorMessage ?? "Please try again."}
              action={{ label: "Try Again", onClick: retry }}
              secondaryAction={{ label: "Cancel", onClick: handleClose }}
            />
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(overlay, document.body ?? document.documentElement);
}
