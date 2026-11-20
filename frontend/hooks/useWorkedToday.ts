"use client";

import { useEffect } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useElapsedSeconds, useRefetchWhileActive } from "@/hooks/useElapsedSeconds";
import { API } from "@/lib/api/endpoints";
import type { TodaySession } from "@/types/attendance";
import { totalAfterPunchOut } from "@/lib/workedTime";

/**
 * Today's worked time for the Home card: the server's figures for today plus the real time passed since they arrived (so a throttled
 * background tab cannot make it fall behind), updated every second while punched in. Re-reads the server whenever `refreshKey`
 * changes (the Home page passes its punch status) or any other part of the app
 * announces an attendance change, so the card follows a punch in or out.
 */
export function useWorkedToday(refreshKey: string) {
  const { data, loading, refetch } = useFetch<TodaySession>(API.attendance.today);
  useEffect(() => { refetch(); }, [refreshKey, refetch]);

  useEffect(() => {
    function handleAttendanceUpdate() { refetch(); }
    window.addEventListener("attendance:updated", handleAttendanceUpdate);
    return () => window.removeEventListener("attendance:updated", handleAttendanceUpdate);
  }, [refetch]);

  const isClockedIn = data?.is_clocked_in ?? false;
  const elapsedSinceLoad = useElapsedSeconds(data, isClockedIn);
  useRefetchWhileActive(refetch, isClockedIn);   // back on the tab, or every few minutes: re-read the server's figure

  return {
    isLoading: loading && !data,
    isClockedIn,
    sessionSeconds: (data?.session_seconds ?? 0) + (isClockedIn ? elapsedSinceLoad : 0),
    totalSeconds: (data?.total_seconds ?? 0) + (isClockedIn ? elapsedSinceLoad : 0),
    // Once out: the saved record's own figure (after the break), so the card shows the same number as the attendance calendar.
    finalSeconds: totalAfterPunchOut(data),
    breakSeconds: data?.break_seconds ?? 0,
    punches: data?.punches ?? [],
  };
}
