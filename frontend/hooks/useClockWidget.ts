"use client";

import { useState, useEffect, useCallback } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import { useFaceVerificationStatus } from "@/hooks/useFaceVerificationStatus";
import type { TodaySession, AttendanceMode, PunchLocation } from "@/types/attendance";

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
  // The server decides everything about Face ID (mode, this person's state, the instruction, the fallback), so this
  // hook never writes its own wording. The org toggle is the single source of truth: when it is off nobody is asked
  // to verify; when it is on, an employee with an approved Face ID must verify, and everyone else is stopped with the
  // server's instruction unless the audited fallback currently allows an office punch without one.
  const { isMandatory, requiresFaceToPunch, fallbackActive, message: faceMessage } = useFaceVerificationStatus();
  const faceVerificationRequired = isMandatory && requiresFaceToPunch;
  const faceRegistrationMissing  = isMandatory && !requiresFaceToPunch && !fallbackActive;
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
        showToast(faceMessage || "Face ID registration is required before you can clock in.", "error");
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
        showToast(e?.message ?? "Punch failed. Please try again.", "error");
        return false;
      } finally {
        setIsPunching(false);
      }
    },
    [showToast, faceRegistrationMissing, faceMessage]
  );

  return {
    session, isLoading: fetchLoading && !session, isPunching, isLocating,
    faceVerificationRequired, faceRegistrationMissing, faceFallbackActive: fallbackActive, prepareLocation, punch,
  };
}
