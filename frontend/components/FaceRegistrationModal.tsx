"use client";

// Shared by the onboarding wizard (first-time capture) and the Profile page
// (re-capture / update an existing registration) — same capture flow, only
// the copy differs, via the `mode` prop.
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useFaceRegistrationCapture } from "@/hooks/useFaceRegistrationCapture";
import FaceStatusPanel from "@/components/FaceStatusPanel";
import FaceCaptureStage from "@/components/FaceCaptureStage";
import FaceConsentPanel from "@/components/FaceConsentPanel";
import { FACE_CONSENT_NOTICE_EMPLOYEE } from "@/lib/faceApi/consentText";

interface FaceRegistrationModalProps {
  onClose: () => void;
  /** "register" (default) — first-time capture, shown during onboarding.
   *  "update" — re-capture to replace an existing registration, shown on the
   *  Profile page, which no longer offers a first-time "Register" action. */
  mode?: "register" | "update";
}

export default function FaceRegistrationModal({ onClose, mode = "register" }: FaceRegistrationModalProps) {
  const { phase, errorMessage, submittedRequest, modelProgress, liveHint, livenessProgress, videoRef, canvasRef, start, retry, stop } = useFaceRegistrationCapture();
  // Gates everything below — the camera never opens (start() is never
  // called) until this is true. Reset per modal open (no persisted "don't
  // ask again"), since mode="update" is a materially new capture, not a
  // continuation of a previous consent.
  const [consentAcknowledged, setConsentAcknowledged] = useState(false);

  function handleClose() {
    stop(); // always release the camera, whatever phase we're in
    onClose();
  }

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleClose is stable enough for an Escape listener
  }, []);

  const showCameraPreview = phase === "detecting" || phase === "liveness_checking" || phase === "capturing_multi";
  const headerTitle = mode === "update" ? "Update My Face" : "Register My Face";
  const idleTitle   = mode === "update" ? "Update your face ID" : "Register your face";
  const idleMessage = mode === "update"
    ? "We'll ask for camera access, run a quick liveness check to confirm it's really you, then send your updated face ID for HR approval. No photo or video is ever sent — only a numeric face signature."
    : "We'll ask for camera access, run a quick liveness check to confirm it's really you, then send your face ID for HR approval. No photo or video is ever sent — only a numeric face signature.";

  const overlay = (
    <div
      className="fixed inset-0 flex items-center justify-center p-6"
      style={{ background: "rgba(0,0,0,0.55)", zIndex: 9999 }}
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
            <p className="text-[14px] font-semibold text-white leading-tight">{headerTitle}</p>
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
          {!consentAcknowledged && (
            <FaceConsentPanel
              noticeText={FACE_CONSENT_NOTICE_EMPLOYEE}
              onAcknowledge={() => setConsentAcknowledged(true)}
              onCancel={handleClose}
            />
          )}

          {consentAcknowledged && (
          <>
          <div style={{ display: showCameraPreview ? "block" : "none" }}>
            <FaceCaptureStage videoRef={videoRef} canvasRef={canvasRef} phase={phase} hint={liveHint} progress={livenessProgress} />
          </div>

          {phase === "idle" && (
            <FaceStatusPanel
              icon="ti-face-id" iconColor="var(--primary)" iconBg="rgba(30,78,140,0.08)"
              title={idleTitle}
              message={idleMessage}
              action={{ label: "Start", onClick: () => start(true) }}
            />
          )}

          {phase === "loading_models" && (
            <FaceStatusPanel
              icon="ti-loader-2" iconColor="var(--primary)" iconBg="rgba(30,78,140,0.08)" spinning
              title="Preparing face recognition" message="Downloading face models (first time only)…" progress={modelProgress}
            />
          )}

          {phase === "requesting_camera" && (
            <FaceStatusPanel
              icon="ti-camera" iconColor="var(--primary)" iconBg="rgba(30,78,140,0.08)" spinning
              title="Requesting camera access" message="Please allow camera access in the browser prompt."
            />
          )}

          {phase === "camera_denied" && (
            <FaceStatusPanel
              icon="ti-camera-off" iconColor="var(--error)" iconBg="rgba(239,68,68,0.08)"
              title="Camera access denied"
              message="Face registration needs your camera. Allow camera access for this site in your browser's settings, then try again."
              action={{ label: "Try Again", onClick: retry }}
              secondaryAction={{ label: "Cancel", onClick: handleClose }}
            />
          )}

          {phase === "liveness_failed" && (
            <FaceStatusPanel
              icon="ti-alert-triangle" iconColor="#b45309" iconBg="rgba(234,179,8,0.12)"
              title="Couldn't confirm you're live"
              message="We didn't detect a natural blink or head turn in time. Make sure you're well-lit and centered, then try again."
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
                ?? "We couldn't get a reliably clear capture — this becomes your permanent face ID reference, so it's worth getting right. Try better lighting and hold steady."
              }
              action={{ label: "Try Again", onClick: retry }}
              secondaryAction={{ label: "Cancel", onClick: handleClose }}
            />
          )}

          {phase === "submitting" && (
            <FaceStatusPanel
              icon="ti-loader-2" iconColor="var(--primary)" iconBg="rgba(30,78,140,0.08)" spinning
              title="Submitting" message="Sending your registration for approval…"
            />
          )}

          {phase === "submitted" && submittedRequest && (
            <FaceStatusPanel
              icon="ti-circle-check" iconColor="#15803d" iconBg="rgba(34,197,94,0.12)"
              title="Registration submitted!"
              message="Your face registration request has been sent to HR for approval. You'll be notified once it's reviewed."
              action={{ label: "Done", onClick: handleClose }}
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
          </>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(overlay, document.body ?? document.documentElement);
}
