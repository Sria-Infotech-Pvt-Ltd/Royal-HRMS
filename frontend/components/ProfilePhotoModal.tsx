"use client";

// Upload-from-device or live-capture a profile display photo. Every member of
// the org uses this from their own Profile tab (see ProfileClient.tsx) —
// self-service, no permission gate. The photo is stored as a plain image on
// the backend (apps.accounts.User.profile_photo), never as a face-embedding
// vector — unrelated to the separate Face ID verification feature.
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useProfilePhotoCapture } from "@/hooks/useProfilePhotoCapture";
import { useProfilePhotoUpload } from "@/hooks/useProfilePhotoUpload";
import FaceStatusPanel from "@/components/FaceStatusPanel";

const ACCEPTED_TYPES = ["image/jpeg", "image/png"];
const ACCEPT_ATTR     = ".jpg,.jpeg,.png,image/jpeg,image/png";
const MIN_SIZE        = 100 * 1024; // 100 KB
const MAX_SIZE        = 200 * 1024; // 200 KB

interface ProfilePhotoModalProps {
  onClose:    () => void;
  onUploaded: (url: string) => void;
  /** Whether the user currently has a photo set — shows a "Remove Photo" option when true. */
  hasExistingPhoto?: boolean;
  onRemoved?: () => void;
}

type Mode = "choose" | "device" | "camera";

export default function ProfilePhotoModal({ onClose, onUploaded, hasExistingPhoto, onRemoved }: ProfilePhotoModalProps) {
  const [mode, setMode]                 = useState<Mode>("choose");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl]     = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const { upload, remove, uploading, error: uploadError } = useProfilePhotoUpload();
  const {
    phase: cameraPhase, errorMessage: cameraError,
    videoRef, canvasRef, start: startCamera, capture, stop: stopCamera,
  } = useProfilePhotoCapture({
    onCaptured: blob => {
      const file = new File([blob], "profile-photo.jpg", { type: "image/jpeg" });
      applySelection(file);
    },
  });

  function applySelection(file: File) {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setValidationError(null);
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  }

  function handleClose() {
    stopCamera();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    onClose();
  }

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleClose is stable enough for an Escape listener
  }, []);

  function handleChooseDevice() {
    setMode("device");
    fileInputRef.current?.click();
  }

  function handleChooseCamera() {
    setMode("camera");
    void startCamera();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    e.target.value = ""; // always reset so choosing the same file twice still fires onChange
    if (!files || files.length === 0) return;
    // The <input> has no `multiple` attribute so the browser only ever offers
    // one, but a defensive check costs nothing and covers pasted/dropped lists.
    if (files.length > 1) {
      setValidationError("Please select only one photo.");
      return;
    }
    const file = files[0];
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setValidationError("Only JPG, JPEG, and PNG files are allowed.");
      return;
    }
    if (file.size < MIN_SIZE || file.size > MAX_SIZE) {
      setValidationError(
        `Image must be between 100 KB and 200 KB (selected file is ${Math.round(file.size / 1024)} KB).`
      );
      return;
    }
    applySelection(file);
  }

  function handleRetake() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setSelectedFile(null);
    setValidationError(null);
    if (mode === "camera") void startCamera();
  }

  async function handleConfirm() {
    if (!selectedFile) return;
    const url = await upload(selectedFile);
    if (url) onUploaded(url);
  }

  async function handleRemove() {
    const ok = await remove();
    if (ok) onRemoved?.();
  }

  const showLiveCamera = mode === "camera" && cameraPhase === "live" && !previewUrl;

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
            <i className="ti ti-user-circle text-white text-[18px]" />
            <p className="text-[14px] font-semibold text-white leading-tight">Profile Photo</p>
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
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT_ATTR}
            className="hidden"
            onChange={handleFileChange}
          />

          {mode === "choose" && (
            <>
              <FaceStatusPanel
                icon="ti-user-circle" iconColor="var(--primary)" iconBg="rgba(30,78,140,0.08)"
                title="Add a profile photo"
                message="JPG, JPEG, or PNG, between 100 KB and 200 KB. Choose one photo, or capture a new one with your camera."
                action={{ label: "Capture Photo", onClick: handleChooseCamera }}
                secondaryAction={{ label: "Upload from Device", onClick: handleChooseDevice }}
              />
              {hasExistingPhoto && (
                <div className="flex justify-center -mt-3">
                  <button
                    type="button"
                    className="text-sm"
                    style={{ color: "var(--error)", background: "none", border: "none", cursor: uploading ? "not-allowed" : "pointer" }}
                    onClick={handleRemove}
                    disabled={uploading}
                    suppressHydrationWarning
                  >
                    {uploading ? "Removing…" : "Remove Current Photo"}
                  </button>
                </div>
              )}
            </>
          )}

          {mode === "camera" && cameraPhase === "requesting_camera" && (
            <FaceStatusPanel
              icon="ti-camera" iconColor="var(--primary)" iconBg="rgba(30,78,140,0.08)" spinning
              title="Requesting camera access" message="Please allow camera access in the browser prompt."
            />
          )}

          {mode === "camera" && cameraPhase === "camera_denied" && (
            <FaceStatusPanel
              icon="ti-camera-off" iconColor="var(--error)" iconBg="rgba(239,68,68,0.08)"
              title="Camera access denied"
              message="Allow camera access for this site in your browser's settings, then try again — or upload a photo from your device instead."
              action={{ label: "Try Again", onClick: handleChooseCamera }}
              secondaryAction={{ label: "Upload Instead", onClick: handleChooseDevice }}
            />
          )}

          {mode === "camera" && cameraPhase === "error" && (
            <FaceStatusPanel
              icon="ti-alert-circle" iconColor="var(--error)" iconBg="rgba(239,68,68,0.08)"
              title="Something went wrong"
              message={cameraError ?? "Please try again."}
              action={{ label: "Try Again", onClick: handleChooseCamera }}
              secondaryAction={{ label: "Cancel", onClick: handleClose }}
            />
          )}

          {showLiveCamera && (
            <div className="flex flex-col items-center">
              <div className="relative rounded-2xl overflow-hidden mx-auto" style={{ width: 320, height: 240, background: "#111" }}>
                <video ref={videoRef} muted playsInline className="w-full h-full object-cover" style={{ transform: "scaleX(-1)" }} />
              </div>
              <canvas ref={canvasRef} className="hidden" />
              <button className="btn btn-primary btn-sm mt-4" suppressHydrationWarning onClick={capture}>
                <i className="ti ti-camera" /> Capture
              </button>
            </div>
          )}

          {previewUrl && (
            <div className="flex flex-col items-center">
              {/* eslint-disable-next-line @next/next/no-img-element -- transient blob: preview URL, not a static/remote asset next/image can optimise */}
              <img
                src={previewUrl}
                alt="Selected profile photo preview"
                className="rounded-2xl object-cover"
                style={{ width: 200, height: 200 }}
              />
              {(validationError || uploadError) && (
                <p className="text-sm mt-3" style={{ color: "var(--error)" }}>{validationError || uploadError}</p>
              )}
              <div className="flex gap-3 mt-4">
                <button className="btn btn-ghost btn-sm" suppressHydrationWarning onClick={handleRetake} disabled={uploading}>
                  {mode === "camera" ? "Retake" : "Choose Another"}
                </button>
                <button className="btn btn-primary btn-sm" suppressHydrationWarning onClick={handleConfirm} disabled={uploading}>
                  {uploading
                    ? <><i className="ti ti-loader-2 animate-spin" /> Uploading…</>
                    : <>Use This Photo</>}
                </button>
              </div>
            </div>
          )}

          {mode === "device" && !previewUrl && validationError && (
            <FaceStatusPanel
              icon="ti-alert-circle" iconColor="var(--error)" iconBg="rgba(239,68,68,0.08)"
              title="That photo won't work"
              message={validationError}
              action={{ label: "Choose Another", onClick: handleChooseDevice }}
              secondaryAction={{ label: "Cancel", onClick: handleClose }}
            />
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(overlay, document.body ?? document.documentElement);
}
