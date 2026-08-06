"use client";

// Thin wrapper around useFaceLivenessCapture: once a face descriptor is
// captured, submits it for HR approval. All the camera/detection/liveness
// engine lives in useFaceLivenessCapture — this hook only owns the
// submit/submitted/error states layered on top of a successful capture.
import { useCallback, useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFaceLivenessCapture, type LivenessCapturePhase } from "@/hooks/useFaceLivenessCapture";
import type { FaceRegistrationRequest, FaceRegistrationSubmitPayload } from "@/types/faceRegistration";

export type CapturePhase = LivenessCapturePhase | "submitting" | "submitted";

interface UseFaceRegistrationCapture {
  phase:            CapturePhase;
  errorMessage:     string | null;
  submittedRequest: FaceRegistrationRequest | null;
  videoRef:         ReturnType<typeof useFaceLivenessCapture>["videoRef"];
  canvasRef:        ReturnType<typeof useFaceLivenessCapture>["canvasRef"];
  start:            () => void;
  retry:            () => void;
  stop:             () => void;
}

export function useFaceRegistrationCapture(): UseFaceRegistrationCapture {
  const [submitPhase, setSubmitPhase]   = useState<"idle" | "submitting" | "submitted" | "error">("idle");
  const [submitError, setSubmitError]   = useState<string | null>(null);
  const [submittedRequest, setSubmittedRequest] = useState<FaceRegistrationRequest | null>(null);
  const stopCaptureRef = useRef<() => void>(() => {});

  const submit = useCallback(async (payload: FaceRegistrationSubmitPayload) => {
    setSubmitPhase("submitting");
    try {
      const res = await clientApi.post<{ data: FaceRegistrationRequest }>(API.attendance.faceRegistration.submit, payload);
      stopCaptureRef.current();
      setSubmittedRequest(res.data.data);
      setSubmitPhase("submitted");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        (err as { message?: string })?.message ??
        "Failed to submit registration. Please try again.";
      setSubmitError(msg);
      setSubmitPhase("error");
    }
  }, []);

  const handleCaptured = useCallback((descriptor: number[], livenessScore: number) => {
    void submit({ face_embedding: descriptor, liveness_passed: true, liveness_score: livenessScore });
  }, [submit]);

  const capture = useFaceLivenessCapture({ onCaptured: handleCaptured });
  useEffect(() => { stopCaptureRef.current = capture.stop; }, [capture.stop]);

  const start = useCallback(() => {
    setSubmitPhase("idle");
    setSubmitError(null);
    setSubmittedRequest(null);
    capture.start();
  }, [capture]);

  const retry = useCallback(() => {
    setSubmitError(null);
    // A failed submission still has the camera live — same "full restart"
    // rule useFaceLivenessCapture's own retry uses for a hard camera error.
    if (submitPhase === "error") {
      setSubmitPhase("idle");
      capture.start();
      return;
    }
    capture.retry();
  }, [capture, submitPhase]);

  const stop = useCallback(() => {
    capture.stop();
    setSubmitPhase("idle");
    setSubmitError(null);
    setSubmittedRequest(null);
  }, [capture]);

  const phase: CapturePhase = submitPhase === "idle" ? capture.phase : submitPhase;
  const errorMessage = submitPhase === "error" ? submitError : capture.errorMessage;

  return {
    phase, errorMessage, submittedRequest,
    videoRef: capture.videoRef, canvasRef: capture.canvasRef,
    start, retry, stop,
  };
}
