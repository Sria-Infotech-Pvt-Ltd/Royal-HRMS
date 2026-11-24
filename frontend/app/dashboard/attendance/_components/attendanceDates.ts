// Pure date helpers for the attendance date picker. They work on the viewer's own calendar days (never through UTC): the earlier
// version built dates at local midnight and read them back with toISOString(), which in India moved every result a day early, so
// "previous day" went back TWO days and "next day" did not move at all.

import { tr } from "@/lib/i18n/tr";
import { localISODate } from "./monthView";

function parts(iso: string): [number, number, number] {
  const [year, month, day] = iso.split("-").map(Number);
  return [year, month, day];
}

/** The date `delta` days from `iso` (negative for earlier), as yyyy-mm-dd. */
export function shiftISODate(iso: string, delta: number): string {
  const [year, month, day] = parts(iso);
  return localISODate(new Date(year, month - 1, day + delta));
}

/** Whole days from `iso` to `todayISO`: 0 today, 1 yesterday, -1 tomorrow. */
export function daysBefore(iso: string, todayISO: string): number {
  const [year, month, day] = parts(iso);
  const [todayYear, todayMonth, todayDay] = parts(todayISO);
  return Math.round((Date.UTC(todayYear, todayMonth - 1, todayDay) - Date.UTC(year, month - 1, day)) / 86_400_000);
}

/** "Today", "Yesterday", "4 days ago", "Tomorrow", "In 3 days". */
export function relativeDayLabel(iso: string, todayISO: string): string {
  const before = daysBefore(iso, todayISO);
  if (before === 0) return tr("Today");
  if (before === 1) return tr("Yesterday");
  if (before === -1) return tr("Tomorrow");
  return before > 1 ? tr("{count} days ago", { count: before }) : tr("In {count} days", { count: -before });
}

/** "Friday". */
export function weekdayName(iso: string): string {
  const [year, month, day] = parts(iso);
  return new Date(year, month - 1, day).toLocaleDateString("en-IN", { weekday: "long" });
}
