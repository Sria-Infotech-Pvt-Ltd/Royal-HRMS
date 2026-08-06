"use client";

// Plain camera capture for a profile display photo — deliberately NOT built
// on useFaceLivenessCapture: no face-api models, no liveness challenge, no
// detection loop. Just getUserMedia + a manual "Capture" button that snapshots
// the current video frame to a canvas and hands back a JPEG Blob. The camera
// lifecycle (open/close) mirrors useFaceLivenessCapture's pattern.
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

export type PhotoCapturePhase =
  | "idle"
  | "requesting_camera"
  | "camera_denied"
  | "live"
  | "error";

interface UseProfilePhotoCaptureOptions {
  /** Fired once per Capture click with a JPEG Blob of the current frame.
   *  The camera is released immediately after — call start() again to retake. */
  onCaptured: (blob: Blob) => void;
}

interface UseProfilePhotoCapture {
  phase:        PhotoCapturePhase;
  errorMessage: string | null;
  videoRef:     RefObject<HTMLVideoElement | null>;
  canvasRef:    RefObject<HTMLCanvasElement | null>;
  start:        () => void;
  capture:      () => void;
  stop:         () => void;
}

const JPEG_QUALITY = 0.85;

export function useProfilePhotoCapture(
  { onCaptured }: UseProfilePhotoCaptureOptions,
): UseProfilePhotoCapture {
  const [phase, setPhase] = useState<PhotoCapturePhase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const videoRef      = useRef<HTMLVideoElement | null>(null);
  const canvasRef     = useRef<HTMLCanvasElement | null>(null);
  const streamRef     = useRef<MediaStream | null>(null);
  const onCapturedRef = useRef(onCaptured);

  useEffect(() => { onCapturedRef.current = onCaptured; }, [onCaptured]);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]); // always release the camera on unmount

  const start = useCallback(async () => {
    setErrorMessage(null);
    setPhase("requesting_camera");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setPhase("live");
    } catch (err: unknown) {
      const name = (err as { name?: string })?.name;
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setPhase("camera_denied");
      } else {
        setErrorMessage("Could not access the camera. Please check it isn't in use by another app.");
        setPhase("error");
      }
    }
  }, []);

  const capture = useCallback(() => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => {
      if (!blob) {
        setErrorMessage("Could not capture the photo. Please try again.");
        setPhase("error");
        return;
      }
      stopCamera();
      setPhase("idle");
      onCapturedRef.current(blob);
    }, "image/jpeg", JPEG_QUALITY);
  }, [stopCamera]);

  const stop = useCallback(() => {
    stopCamera();
    setPhase("idle");
    setErrorMessage(null);
  }, [stopCamera]);

  return { phase, errorMessage, videoRef, canvasRef, start, capture, stop };
}
