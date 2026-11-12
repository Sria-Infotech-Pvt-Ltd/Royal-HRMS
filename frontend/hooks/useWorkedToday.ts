"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { TodaySession } from "@/types/attendance";

/**
 * Today's worked time for the Home card: the server's figures for today, ticking
 * once a second while punched in. Re-reads the server whenever `refreshKey`
 * changes (the Home page passes its punch status) or any other part of the app
 * announces an attendance change, so the card follows a punch in or out.
 */
export function useWorkedToday(refreshKey: string) {
  const { data, loading, refetch } = useFetch<TodaySession>(API.attendance.today);
  const [elapsedSinceLoad, setElapsedSinceLoad] = useState(0);

  useEffect(() => { refetch(); }, [refreshKey, refetch]);

  useEffect(() => {
    function handleAttendanceUpdate() { refetch(); }
    window.addEventListener("attendance:updated", handleAttendanceUpdate);
    return () => window.removeEventListener("attendance:updated", handleAttendanceUpdate);
  }, [refetch]);

  const isClockedIn = data?.is_clocked_in ?? false;

  // Restart the local tick from zero each time fresh server numbers arrive.
  useEffect(() => { setElapsedSinceLoad(0); }, [data]);

  useEffect(() => {
    if (!isClockedIn) return;
    const id = setInterval(() => setElapsedSinceLoad(seconds => seconds + 1), 1000);
    return () => clearInterval(id);
  }, [isClockedIn, data]);

  return {
    isLoading: loading && !data,
    isClockedIn,
    sessionSeconds: (data?.session_seconds ?? 0) + (isClockedIn ? elapsedSinceLoad : 0),
    totalSeconds: (data?.total_seconds ?? 0) + (isClockedIn ? elapsedSinceLoad : 0),
    punches: data?.punches ?? [],
  };
}
