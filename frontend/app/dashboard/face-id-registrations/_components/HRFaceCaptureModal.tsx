"use client";

// HR captures a face in person (e.g. during onboarding) and registers or
// replaces an employee's face ID — same portal/phase-panel shape as
// FaceRegistrationModal.tsx, driven by useHRFaceCapture instead of
// useFaceRegistrationCapture (posts to a different, HR-only endpoint with a
// target employee instead of the caller's own identity).
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useHRFaceCapture } from "@/hooks/useHRFaceRegistration";
import FaceStatusPanel from "@/components/FaceStatusPanel";
import FaceCaptureStage from "@/components/FaceCaptureStage";
import FaceConsentPanel from "@/components/FaceConsentPanel";
import { FACE_CONSENT_NOTICE_HR } from "@/lib/faceApi/consentText";
import { useT } from "@/hooks/useI18n";

interface HRFaceCaptureModalProps {
  employeeUuid: string;
  employeeName: string;
  isUpdate:     boolean; // true when this employee already has an approved face ID
  onClose:      () => void;
  onRegistered: () => void; // called once the new registration is saved
}

export default function HRFaceCaptureModal({
  employeeUuid, employeeName, isUpdate, onClose, onRegistered,
}: HRFaceCaptureModalProps) {
  const { phase, errorMessage, registeredRequest, modelProgress, liveHint, livenessProgress, videoRef, canvasRef, start, retry, stop } =
    useHRFaceCapture(employeeUuid);
  const [consentAcknowledged, setConsentAcknowledged] = useState(false);
  const t = useT();

  function handleClose() {
    stop(); // always release the camera, whatever phase we're in
    onClose();
  }

  useEffect(() => {
    if (phase === "submitted") onRegistered();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onRegistered is a parent callback; only phase should re-trigger this
  }, [phase]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleClose is stable enough for an Escape listener
  }, []);

  const showCameraPreview = phase === "detecting" || phase === "liveness_checking" || phase === "capturing_multi";

  const overlay = (
    <div
      className="fixed inset-0 flex items-center justify-center p-6"
      style={{ background: "rgba(0,0,0,0.55)", zIndex: 9999 }}
      onClick={handleClose}
    >
      <div
        className="relative flex flex-col rounded-2xl overflow-hidden shadow-2xl"
        style={{ background: "var(--surface)", width: "min(440px, 92vw)" }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 flex-shrink-0" style={{ background: "var(--primary)" }}>
          <div className="flex items-center gap-2.5">
            <i className="ti ti-face-id text-white text-[18px]" />
            <p className="text-[14px] font-semibold text-white leading-tight">
              {isUpdate ? t("Update Face ID — {name}", { name: employeeName }) : t("Register Face ID — {name}", { name: employeeName })}
            </p>
          </div>
          <button
            onClick={handleClose}
            suppressHydrationWarning
            aria-label={t("Close")}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-white/80 hover:bg-white/15 transition-colors"
          >
            <i className="ti ti-x text-[18px]" />
          </button>
        </div>

        <div className="p-6" style={{ minHeight: 260 }}>
          {!consentAcknowledged && (
            <FaceConsentPanel
              noticeText={FACE_CONSENT_NOTICE_HR}
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
              icon="ti-face-id" iconColor="var(--primary)" iconBg="color-mix(in srgb, var(--brand) 8%, transparent)"
              title={isUpdate ? t("Update {name}'s face", { name: employeeName }) : t("Register {name}'s face", { name: employeeName })}
              message={
                isUpdate
                  ? t("This will replace their currently registered face ID. Position them in front of the camera and start when ready.")
                  : t("Have the employee sit in front of this camera, then start — a quick liveness check confirms it's really them before it's saved.")
              }
              action={{ label: t("Start"), onClick: () => start(true) }}
            />
          )}

          {phase === "loading_models" && (
            <FaceStatusPanel
              icon="ti-loader-2" iconColor="var(--primary)" iconBg="color-mix(in srgb, var(--brand) 8%, transparent)" spinning
              title={t("Preparing face recognition")} message={t("Downloading face models (first time only)…")} progress={modelProgress}
            />
          )}

          {phase === "requesting_camera" && (
            <FaceStatusPanel
              icon="ti-camera" iconColor="var(--primary)" iconBg="color-mix(in srgb, var(--brand) 8%, transparent)" spinning
              title={t("Requesting camera access")} message={t("Please allow camera access in the browser prompt.")}
            />
          )}

          {phase === "camera_denied" && (
            <FaceStatusPanel
              icon="ti-camera-off" iconColor="var(--error)" iconBg="rgba(239,68,68,0.08)"
              title={t("Camera access denied")}
              message={t("Registering a face ID needs camera access. Allow it for this site in your browser's settings, then try again.")}
              action={{ label: t("Try Again"), onClick: retry }}
              secondaryAction={{ label: t("Cancel"), onClick: handleClose }}
            />
          )}

          {phase === "liveness_failed" && (
            <FaceStatusPanel
              icon="ti-alert-triangle" iconColor="#b45309" iconBg="rgba(234,179,8,0.12)"
              title={t("Couldn't confirm they're live")}
              message={t("Registration needs both a natural blink and a slight head turn, and we didn't see both in time. Make sure they're well-lit and centered, then try again.")}
              action={{ label: t("Try Again"), onClick: retry }}
              secondaryAction={{ label: t("Cancel"), onClick: handleClose }}
            />
          )}

          {phase === "quality_failed" && (
            <FaceStatusPanel
              icon="ti-alert-triangle" iconColor="#b45309" iconBg="rgba(234,179,8,0.12)"
              title={t("Capture wasn't clear enough")}
              message={
                errorMessage
                ?? t("We couldn't get a reliably clear capture — this becomes their permanent face ID reference, so it's worth getting right. Try better lighting and have them hold steady.")
              }
              action={{ label: t("Try Again"), onClick: retry }}
              secondaryAction={{ label: t("Cancel"), onClick: handleClose }}
            />
          )}

          {phase === "submitting" && (
            <FaceStatusPanel
              icon="ti-loader-2" iconColor="var(--primary)" iconBg="color-mix(in srgb, var(--brand) 8%, transparent)" spinning
              title={t("Saving")} message={t("Registering face ID…")}
            />
          )}

          {phase === "submitted" && registeredRequest && (
            <FaceStatusPanel
              icon="ti-circle-check" iconColor="#15803d" iconBg="rgba(34,197,94,0.12)"
              title={t("Face ID registered!")}
              message={t("{name}'s face ID is approved and active immediately — no further review needed.", { name: employeeName })}
              action={{ label: t("Done"), onClick: handleClose }}
            />
          )}

          {phase === "error" && (
            <FaceStatusPanel
              icon="ti-alert-circle" iconColor="var(--error)" iconBg="rgba(239,68,68,0.08)"
              title={t("Something went wrong")}
              message={errorMessage ?? t("Please try again.")}
              action={{ label: t("Try Again"), onClick: retry }}
              secondaryAction={{ label: t("Cancel"), onClick: handleClose }}
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
