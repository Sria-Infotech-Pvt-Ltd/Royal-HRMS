"use client";

// Data/mutation hooks behind the HR "Face ID Registrations" page
// (app/dashboard/face-id-registrations) — keeps the page and its capture
// modal free of direct API calls, per project convention.
import { useCallback, useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { useFaceLivenessCapture, type LivenessCapturePhase, type CaptureQualityMeta } from "@/hooks/useFaceLivenessCapture";
import type {
  FaceRegistrationEmployee,
  FaceRegistrationRequest,
  PaginatedFaceRegistrationEmployees,
} from "@/types/faceRegistration";

// Same reasoning as useFaceRegistrationCapture.ts's own constants — an
// HR-captured face is just as much a permanent verification reference as a
// self-submitted one, so it gets the same stricter capture bar.
const REGISTRATION_FRAMES_TO_CAPTURE = 4;
const REGISTRATION_NORMALIZE_LIGHTING = true;

/** Org-wide employee picker — re-fetches as `search` changes. */
export function useFaceRegistrationEmployeePicker(search: string) {
  const { data, loading, error } = useFetch<PaginatedFaceRegistrationEmployees>(
    API.attendance.faceRegistration.employees(search)
  );
  const employees: FaceRegistrationEmployee[] = data?.results ?? [];
  return { employees, loading, error };
}

/** A specific employee's current face-registration status (none/pending/approved/rejected). */
export function useEmployeeFaceStatus(employeeUuid: string | null) {
  const { data, loading, error, refetch } = useFetch<Partial<FaceRegistrationRequest>>(
    employeeUuid ? API.attendance.faceRegistration.employeeStatus(employeeUuid) : null
  );
  return { status: data, loading, error, refetch };
}

export type HRCapturePhase = LivenessCapturePhase | "submitting" | "submitted";

interface UseHRFaceCapture {
  phase:             HRCapturePhase;
  errorMessage:      string | null;
  registeredRequest: FaceRegistrationRequest | null;
  videoRef:          ReturnType<typeof useFaceLivenessCapture>["videoRef"];
  canvasRef:         ReturnType<typeof useFaceLivenessCapture>["canvasRef"];
  /** No-op (does not open the camera) if consentAcknowledged is false — see
   *  useFaceRegistrationCapture's identical guard for the reasoning. */
  start:             (consentAcknowledged: boolean) => void;
  retry:             () => void;
  stop:              () => void;
}

/**
 * Captures a face for a specific employee (HR sitting with them in person)
 * and registers it — auto-approved, since HR directly witnessed the capture.
 * Same submitting/submitted/error-layered-on-capture shape as
 * useFaceRegistrationCapture.ts, just posting to a different endpoint with
 * a target employee_uuid instead of the caller's own identity.
 */
export function useHRFaceCapture(employeeUuid: string | null): UseHRFaceCapture {
  const [submitPhase, setSubmitPhase] = useState<"idle" | "submitting" | "submitted" | "error">("idle");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [registeredRequest, setRegisteredRequest] = useState<FaceRegistrationRequest | null>(null);
  const stopCaptureRef = useRef<() => void>(() => {});
  const consentAcknowledgedRef = useRef(false);

  const submit = useCallback(async (descriptor: number[], livenessScore: number, captureQuality?: CaptureQualityMeta) => {
    if (!employeeUuid) return;
    setSubmitPhase("submitting");
    try {
      const res = await clientApi.post<{ data: FaceRegistrationRequest }>(API.attendance.faceRegistration.register, {
        employee_uuid:        employeeUuid,
        face_embedding:       descriptor,
        liveness_passed:      true,
        liveness_score:       livenessScore,
        consent_acknowledged: consentAcknowledgedRef.current,
        capture_frame_count:  captureQuality?.frameCount,
        capture_variance:     captureQuality?.variance,
      });
      stopCaptureRef.current();
      setRegisteredRequest(res.data.data);
      setSubmitPhase("submitted");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        (err as { message?: string })?.message ??
        "Failed to register face ID. Please try again.";
      setSubmitError(msg);
      setSubmitPhase("error");
    }
  }, [employeeUuid]);

  const handleCaptured = useCallback(
    (descriptor: number[], livenessScore: number, _captureSessionId: string, captureQuality?: CaptureQualityMeta) => {
      void submit(descriptor, livenessScore, captureQuality);
    },
    [submit],
  );

  const capture = useFaceLivenessCapture({
    onCaptured: handleCaptured,
    framesToCapture: REGISTRATION_FRAMES_TO_CAPTURE,
    normalizeLighting: REGISTRATION_NORMALIZE_LIGHTING,
  });
  useEffect(() => { stopCaptureRef.current = capture.stop; }, [capture.stop]);

  const start = useCallback((consentAcknowledged: boolean) => {
    if (!consentAcknowledged) {
      console.error("[useHRFaceCapture] start() called without consent acknowledged — refusing to open the camera.");
      return;
    }
    consentAcknowledgedRef.current = true;
    setSubmitPhase("idle");
    setSubmitError(null);
    setRegisteredRequest(null);
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
    setRegisteredRequest(null);
  }, [capture]);

  const phase: HRCapturePhase = submitPhase === "idle" ? capture.phase : submitPhase;
  const errorMessage = submitPhase === "error" ? submitError : capture.errorMessage;

  return {
    phase, errorMessage, registeredRequest,
    videoRef: capture.videoRef, canvasRef: capture.canvasRef,
    start, retry, stop,
  };
}
