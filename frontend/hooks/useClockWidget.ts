"use client";

import { useState, useEffect, useCallback } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import { useFaceVerificationStatus } from "@/hooks/useFaceVerificationStatus";
import type { TodaySession, AttendanceMode } from "@/types/attendance";
import type { FaceRegistrationRequest } from "@/types/faceRegistration";

const _REGISTRATION_MESSAGES: Record<string, string> = {
  pending:  "Your face ID registration is pending HR approval. You can clock in once it's approved.",
  rejected: "Your face ID registration was rejected. Please register again from your Profile page.",
};
const _REGISTRATION_MISSING_MESSAGE =
  "Face ID registration is mandatory. Please register your face ID from your Profile page before clocking in.";

type NormalisedError = { message?: string };

function parseBrowser(): string {
  if (typeof navigator === "undefined") return "Unknown";
  const ua = navigator.userAgent;
  if (ua.includes("Edg"))     return "Edge";
  if (ua.includes("Chrome"))  return "Chrome";
  if (ua.includes("Firefox")) return "Firefox";
  if (ua.includes("Safari"))  return "Safari";
  if (ua.includes("Opera"))   return "Opera";
  return "Unknown";
}

function parseOS(): string {
  if (typeof navigator === "undefined") return "Unknown";
  const ua = navigator.userAgent;
  if (ua.includes("Windows NT 10")) return "Windows 11/10";
  if (ua.includes("Windows"))       return "Windows";
  if (ua.includes("Mac OS X"))      return "macOS";
  if (ua.includes("Android"))       return "Android";
  if (ua.includes("iPhone"))        return "iOS";
  if (ua.includes("Linux"))         return "Linux";
  return "Unknown";
}

export function useClockWidget() {
  const { showToast } = useToast();
  const { data: todayData, loading: fetchLoading, refetch } = useFetch<TodaySession>(API.attendance.today);
  // Backend returns {} (not an actual registration) when the employee has
  // never submitted one — .status only ever matches "approved" for a real one.
  const { data: faceStatus } = useFetch<Partial<FaceRegistrationRequest>>(API.attendance.faceRegistration.me);
  const { isMandatory } = useFaceVerificationStatus();
  const isApproved = faceStatus?.status === "approved";
  // Org toggle is the single source of truth (see AttendanceFaceVerificationRules
  // on the backend) — when it's off, nobody is asked to verify, even someone
  // approved from before; when it's on, an approved employee must verify and
  // everyone else is blocked from punching until they register (see punch() below).
  const faceVerificationRequired = isMandatory && isApproved;
  const faceRegistrationMissing  = isMandatory && !isApproved;
  const [session, setSession] = useState<TodaySession | null>(null);
  const [isPunching, setIsPunching] = useState(false);
  const [isLocating, setIsLocating] = useState(false);

  useEffect(() => {
    if (todayData) setSession(todayData);
  }, [todayData]);

  useEffect(() => {
    function handleAttendanceUpdate() { refetch(); }
    window.addEventListener("attendance:updated", handleAttendanceUpdate);
    return () => window.removeEventListener("attendance:updated", handleAttendanceUpdate);
  }, [refetch]);

  const isClockedIn = session?.is_clocked_in ?? false;

  useEffect(() => {
    if (!isClockedIn) return;
    const id = setInterval(() => {
      setSession(prev =>
        prev
          ? { ...prev, session_seconds: prev.session_seconds + 1, total_seconds: prev.total_seconds + 1 }
          : prev
      );
    }, 1000);
    return () => clearInterval(id);
  }, [isClockedIn]);

  const punch = useCallback(
    async (
      punchType: "IN" | "OUT",
      attendanceMode: AttendanceMode = "office",
      faceEmbedding?: number[],
      livenessScore?: number,
      captureSessionId?: string,
    ): Promise<boolean> => {
      if (faceRegistrationMissing) {
        const message = (faceStatus?.status && _REGISTRATION_MESSAGES[faceStatus.status])
          ?? _REGISTRATION_MISSING_MESSAGE;
        showToast(message, "error");
        return false;
      }

      setIsPunching(true);
      let latitude: number | null = null;
      let longitude: number | null = null;
      let accuracy: number | null = null;

      if (attendanceMode === "office") {
        if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
          showToast("Your browser does not support location access.", "error");
          setIsPunching(false);
          return false;
        }

        setIsLocating(true);
        try {
          const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
          });
          latitude  = pos.coords.latitude;
          longitude = pos.coords.longitude;
          accuracy  = pos.coords.accuracy;
        } catch (geoErr: unknown) {
          const isPermissionDenied = (geoErr as GeolocationPositionError).code === 1;
          showToast(
            isPermissionDenied
              ? "Location access is required for office clock-in. Please allow location in your browser settings."
              : "Unable to determine your location. Please check your device's location settings and try again.",
            "error"
          );
          setIsLocating(false);
          setIsPunching(false);
          return false;
        }
        setIsLocating(false);
      }

      try {
        const res = await clientApi.post(API.attendance.punch, {
          punch_type:      punchType,
          attendance_mode: attendanceMode,
          source:          "web",
          latitude,
          longitude,
          accuracy,
          device_time:      new Date().toISOString(),
          browser:          parseBrowser(),
          operating_system: parseOS(),
          face_embedding:      faceEmbedding ?? null,
          // Only meaningful alongside face_embedding — see
          // FaceVerificationService.verify_for_punch's anti-replay check.
          liveness_passed:     faceEmbedding ? true : null,
          liveness_score:      livenessScore ?? null,
          capture_session_id:  captureSessionId ?? "",
        });
        const envelope = res.data as { message?: string; data?: TodaySession };
        if (envelope.data) setSession(envelope.data);
        showToast(
          envelope.message ?? (punchType === "IN" ? "Clocked in successfully." : "Clocked out successfully."),
          "success"
        );
        return true;
      } catch (err: unknown) {
        const e = err as NormalisedError;
        showToast(e?.message ?? "Punch failed. Please try again.", "error");
        return false;
      } finally {
        setIsPunching(false);
      }
    },
    [showToast, faceRegistrationMissing, faceStatus]
  );

  return {
    session, isLoading: fetchLoading && !session, isPunching, isLocating,
    faceVerificationRequired, faceRegistrationMissing, punch,
  };
}
