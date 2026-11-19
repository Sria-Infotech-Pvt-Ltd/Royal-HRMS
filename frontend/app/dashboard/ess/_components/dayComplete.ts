// Pure helpers for the "Today completed" state of the Home hero.
import type { AttendanceStatus } from "@/types/employeeDashboard";

/** The day counts as completed once the employee has punched in AND is now punched out. */
export function isDayComplete(status: AttendanceStatus | null): boolean {
  return Boolean(status && !status.clocked_in && status.clock_in_time && status.clock_out_time);
}

/** "08:52" (HH:MM, as the server sends worked time) → "8h 52m"; anything unreadable → "—". */
export function formatWorked(hhmm: string | null | undefined): string {
  const match = /^(\d+):(\d{2})$/.exec(hhmm ?? "");
  if (!match) return "—";
  return `${Number(match[1])}h ${match[2]}m`;
}
