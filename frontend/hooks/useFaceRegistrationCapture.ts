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
  /** No-ops (does not open the camera) if consentAcknowledged is false —
   *  the caller (FaceRegistrationModal) is expected to gate the "Start"
   *  action behind its own consent screen, but this guard exists so the
   *  hook can never submit a capture without consent even if that gating
   *  is ever bypassed by a future caller. */
  start:            (consentAcknowledged: boolean) => void;
  retry:            () => void;
  stop:             () => void;
}

export function useFaceRegistrationCapture(): UseFaceRegistrationCapture {
  const [submitPhase, setSubmitPhase]   = useState<"idle" | "submitting" | "submitted" | "error">("idle");
  const [submitError, setSubmitError]   = useState<string | null>(null);
  const [submittedRequest, setSubmittedRequest] = useState<FaceRegistrationRequest | null>(null);
  const stopCaptureRef = useRef<() => void>(() => {});
  // Set once per session by start(consentAcknowledged) below, read only when
  // a capture actually completes (handleCaptured) — by construction that's
  // always after start() already ran, so this is never stale/unset at read time.
  const consentAcknowledgedRef = useRef(false);

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
    void submit({
      face_embedding: descriptor,
      liveness_passed: true,
      liveness_score: livenessScore,
      consent_acknowledged: consentAcknowledgedRef.current,
    });
  }, [submit]);

  const capture = useFaceLivenessCapture({ onCaptured: handleCaptured });
  useEffect(() => { stopCaptureRef.current = capture.stop; }, [capture.stop]);

  const start = useCallback((consentAcknowledged: boolean) => {
    if (!consentAcknowledged) {
      // Should be unreachable — FaceRegistrationModal only renders the
      // "Start" action after its own consent screen is acknowledged. Logged
      // rather than silently ignored so a future caller that skips the
      // consent screen fails loudly in the console, not just mysteriously
      // never opens the camera.
      console.error("[useFaceRegistrationCapture] start() called without consent acknowledged — refusing to open the camera.");
      return;
    }
    consentAcknowledgedRef.current = true;
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
