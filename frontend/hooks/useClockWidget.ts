"use client";

import { useState, useEffect, useCallback } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import { useFaceVerificationStatus } from "@/hooks/useFaceVerificationStatus";
import type { TodaySession, AttendanceMode, PunchLocation } from "@/types/attendance";
import type { FaceRegistrationRequest } from "@/types/faceRegistration";

const _REGISTRATION_MESSAGES: Record<string, string> = {
  pending:  "Your face ID registration is pending HR approval. You can clock in once it's approved.",
  rejected: "Your face ID registration was rejected. Please register again from your Profile page.",
};
const _REGISTRATION_MISSING_MESSAGE =
  "Face ID registration is mandatory. Please register your face ID from your Profile page before clocking in.";

type NormalisedError = { message?: string; data?: { blocked?: boolean; retry_after_seconds?: number } };

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

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
  // Set once the backend reports the face-verification attempt cap has
  // tripped (FaceVerificationBlockedError, services_face_matching.py) — an
  // epoch-ms deadline, not just a boolean, so the button can show a live
  // countdown instead of a static "try later" that gives no sense of when.
  // Until this passes, punch() refuses to even call the API — see FR-E-18's
  // QA finding that nothing previously stopped a retry click from just
  // repeating the same rejection over and over, indistinguishable from an
  // ordinary mismatch.
  const [lockoutUntil, setLockoutUntil] = useState<number | null>(null);
  const [lockoutSecondsRemaining, setLockoutSecondsRemaining] = useState(0);

  useEffect(() => {
    if (!lockoutUntil) return;
    const tick = () => {
      const remaining = Math.ceil((lockoutUntil - Date.now()) / 1000);
      if (remaining <= 0) {
        setLockoutUntil(null);
        setLockoutSecondsRemaining(0);
      } else {
        setLockoutSecondsRemaining(remaining);
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [lockoutUntil]);

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

  // Fetches GPS and validates it against the employee's geofence via a
  // read-only backend check — BEFORE any face verification modal opens.
  // Mirrors the order the voice flow enforces in conversation_clock_in_face.
  // start_voice_clock_punch (geofence check, then facial proof): callers
  // must call this first and only proceed to the face step (or straight to
  // punch()) once `ok` comes back true. Modes other than "office" don't
  // carry a geofence, so they pass through with no location captured.
  const prepareLocation = useCallback(
    async (attendanceMode: AttendanceMode): Promise<{ ok: boolean; location: PunchLocation | null }> => {
      if (attendanceMode !== "office") return { ok: true, location: null };

      if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
        showToast("Your browser does not support location access.", "error");
        return { ok: false, location: null };
      }

      setIsLocating(true);
      let location: PunchLocation;
      try {
        const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
        });
        location = { latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy };
      } catch (geoErr: unknown) {
        const isPermissionDenied = (geoErr as GeolocationPositionError).code === 1;
        showToast(
          isPermissionDenied
            ? "Location access is required for office clock-in. Please allow location in your browser settings."
            : "Unable to determine your location. Please check your device's location settings and try again.",
          "error"
        );
        setIsLocating(false);
        return { ok: false, location: null };
      }

      try {
        await clientApi.post(API.attendance.geofenceCheck, {
          attendance_mode: attendanceMode,
          latitude:  location.latitude,
          longitude: location.longitude,
          accuracy:  location.accuracy,
        });
      } catch (err: unknown) {
        const e = err as NormalisedError;
        showToast(e?.message ?? "You are outside the allowed location for this branch.", "error");
        setIsLocating(false);
        return { ok: false, location: null };
      }

      setIsLocating(false);
      return { ok: true, location };
    },
    [showToast]
  );

  const punch = useCallback(
    async (
      punchType: "IN" | "OUT",
      attendanceMode: AttendanceMode = "office",
      location: PunchLocation | null = null,
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

      if (lockoutUntil && Date.now() < lockoutUntil) {
        showToast(
          `Too many failed face verification attempts. Please wait ${formatCountdown(lockoutSecondsRemaining)} before trying again.`,
          "error"
        );
        return false;
      }

      setIsPunching(true);
      try {
        const res = await clientApi.post(API.attendance.punch, {
          punch_type:      punchType,
          attendance_mode: attendanceMode,
          source:          "web",
          latitude:  location?.latitude  ?? null,
          longitude: location?.longitude ?? null,
          accuracy:  location?.accuracy  ?? null,
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
        if (e?.data?.blocked && typeof e.data.retry_after_seconds === "number") {
          setLockoutUntil(Date.now() + e.data.retry_after_seconds * 1000);
        }
        showToast(e?.message ?? "Punch failed. Please try again.", "error");
        return false;
      } finally {
        setIsPunching(false);
      }
    },
    [showToast, faceRegistrationMissing, faceStatus, lockoutUntil, lockoutSecondsRemaining]
  );

  return {
    session, isLoading: fetchLoading && !session, isPunching, isLocating,
    faceVerificationRequired, faceRegistrationMissing, prepareLocation, punch,
    isLockedOut: lockoutUntil !== null, lockoutSecondsRemaining,
  };
}
