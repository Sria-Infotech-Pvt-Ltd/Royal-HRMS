import type { WeeklyAttendanceDay } from "@/types/dashboard";

/** Bar labels for the "Attendance this week" chart, Monday first. */
export const MONDAY_FIRST_LABELS = ["M", "T", "W", "T", "F", "S", "S"] as const;

export interface WeekBar {
  label: string;
  /** Employees present that day; null for a day later this week (no data yet). */
  count: number | null;
  isToday: boolean;
}

/**
 * Rearranges the dashboard's weekly_attendance series into this week's
 * Monday-to-Sunday order. The backend sends the last 7 calendar days, oldest
 * first, ending with today, so Monday..today are always inside it; the days
 * after today have no data yet and come back with count null.
 */
export function toCurrentWeek(lastSevenDays: WeeklyAttendanceDay[], today: Date): WeekBar[] {
  const todayIndex = (today.getDay() + 6) % 7; // 0 = Monday … 6 = Sunday
  const lastIndex = lastSevenDays.length - 1;
  return MONDAY_FIRST_LABELS.map((label, index) => {
    const daysAgo = todayIndex - index;
    const source = daysAgo >= 0 ? lastSevenDays[lastIndex - daysAgo] : undefined;
    return { label, count: source ? source.count : null, isToday: daysAgo === 0 };
  });
}
