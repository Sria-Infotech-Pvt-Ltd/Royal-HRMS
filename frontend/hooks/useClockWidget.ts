"use client";

import { useState, useEffect, useCallback } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import type { TodaySession, AttendanceMode } from "@/types/attendance";

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
  const { data: todayData, loading: fetchLoading } = useFetch<TodaySession>(API.attendance.today);
  const [session, setSession] = useState<TodaySession | null>(null);
  const [isPunching, setIsPunching] = useState(false);
  const [isLocating, setIsLocating] = useState(false);

  useEffect(() => {
    if (todayData) setSession(todayData);
  }, [todayData]);

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
    async (punchType: "IN" | "OUT", attendanceMode: AttendanceMode = "office") => {
      setIsPunching(true);
      let latitude: number | null = null;
      let longitude: number | null = null;
      let accuracy: number | null = null;

      if (attendanceMode === "office") {
        if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
          showToast("Your browser does not support location access.", "error");
          setIsPunching(false);
          return;
        }

        setIsLocating(true);
        try {
          const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 10000, maximumAge: 0 });
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
          return;
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
        });
        const envelope = res.data as { message?: string; data?: TodaySession };
        if (envelope.data) setSession(envelope.data);
        showToast(
          envelope.message ?? (punchType === "IN" ? "Clocked in successfully." : "Clocked out successfully."),
          "success"
        );
      } catch (err: unknown) {
        const e = err as NormalisedError;
        showToast(e?.message ?? "Punch failed. Please try again.", "error");
      } finally {
        setIsPunching(false);
      }
    },
    [showToast]
  );

  return { session, isLoading: fetchLoading && !session, isPunching, isLocating, punch };
}
