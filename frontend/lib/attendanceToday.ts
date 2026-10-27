// "My Attendance Today" card — what to show for GET /attendance/today/.
// The endpoint is always the signed-in user's own day (TodayAttendanceView
// reads request.user only); this just turns its response into display state.

import type { AttendancePunch, AttendanceToday } from "@/types/dashboard";

export type TodayView =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "empty" }
  | { kind: "present"; isClockedIn: boolean; firstIn: string; lastOut: string; total: string; punches: AttendancePunch[] };

export function formatSeconds(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h}h ${m}m`;
}

export function todayView(
  data: AttendanceToday | null | undefined, loading: boolean, error: string | null | undefined,
): TodayView {
  // Keep showing the last good data while a refresh is in flight.
  if (loading && !data) return { kind: "loading" };
  if (error && !data) return { kind: "error", message: "Couldn't load today's attendance." };
  if (!data || data.punches.length === 0) return { kind: "empty" };
  const firstIn = data.punches.find(p => p.type === "IN");
  const lastOut = [...data.punches].reverse().find(p => p.type === "OUT");
  return {
    kind: "present",
    isClockedIn: data.is_clocked_in ?? false,
    firstIn: firstIn?.time ?? "—",
    lastOut: lastOut?.time ?? "—",
    total: data.total_seconds > 0 ? formatSeconds(data.total_seconds) : "—",
    punches: data.punches,
  };
}
