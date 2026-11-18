// Pure helpers and shared types for the Employee Month View. No React.

import { PALETTE, tint } from "./attendancePalette";

export interface EmployeeOption {
  id: string;
  employee_id: string;
  full_name: string;
  department: string;
  designation: string;
}

export interface DayRecord {
  date: string;
  day_short: string;
  day_num: number;
  status: string;
  status_label: string;
  clock_in: string | null;
  clock_out: string | null;
  total_hours: number;
  is_flagged: boolean;
  record_id: string | null;
}

export interface MonthStats {
  present: number;
  late: number;
  half_day: number;
  absent: number;
  on_leave: number;
  lop_days: number;
  total_hours: number;
}

export interface MonthData {
  employee: EmployeeOption;
  month: string;
  stats: MonthStats;
  days: DayRecord[];
}

export interface StatusMeta { label: string; short: string; colour: string; bg: string }

const meta = (label: string, short: string, colour: string, alpha = 0.14): StatusMeta => ({ label, short, colour, bg: tint(colour, alpha) });

export const STATUS_META: Record<string, StatusMeta> = {
  present: meta("Present", "P", PALETTE.present),
  late: meta("Late", "Late", PALETTE.late),
  half_day: meta("Half Day", "½", PALETTE.half_day),
  on_leave: meta("On Leave", "OL", PALETTE.on_leave),
  absent: meta("Absent", "A", PALETTE.absent),
  incomplete: meta("Incomplete", "Inc", PALETTE.incomplete),
  weekly_off: meta("Week Off", "WO", PALETTE.weekly_off, 0.14),
  holiday: meta("Holiday", "Hol", PALETTE.holiday),
  // A past working day with nothing recorded: slate on a barely-there tint, not a warning colour, so a month of them is not alarming.
  no_record: meta("Not marked", "?", PALETTE.not_marked, 0.05),
  // A day that has not happened yet: no tint at all, nothing to show.
  future: { label: "Upcoming", short: "", colour: PALETTE.future, bg: "transparent" },
};

/** The statuses a person can filter the month by, in reading order. */
export const FILTER_STATUSES = ["present", "late", "half_day", "on_leave", "absent", "incomplete", "no_record", "weekly_off", "holiday"] as const;

/** The viewer's own calendar date as yyyy-mm-dd (not UTC: just after midnight in India the UTC date is still yesterday). */
export function localISODate(date: Date = new Date()): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function currentMonthISO(now: Date = new Date()): string {
  return localISODate(now).slice(0, 7);
}

export function shiftMonth(month: string, delta: number): string {
  const [year, monthNumber] = month.split("-").map(Number);
  const shifted = new Date(year, monthNumber - 1 + delta, 1);
  return `${shifted.getFullYear()}-${String(shifted.getMonth() + 1).padStart(2, "0")}`;
}

export function formatMonthLabel(month: string): string {
  const [year, monthNumber] = month.split("-").map(Number);
  return new Date(year, monthNumber - 1, 1).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

/** Weeks of seven cells, Monday first, with null padding before the 1st and after the last day. */
export function buildGrid(days: DayRecord[], month: string): (DayRecord | null)[][] {
  const [year, monthNumber] = month.split("-").map(Number);
  const pad = (new Date(year, monthNumber - 1, 1).getDay() + 6) % 7;
  const cells: (DayRecord | null)[] = [...Array<null>(pad).fill(null), ...days];
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks: (DayRecord | null)[][] = [];
  for (let index = 0; index < cells.length; index += 7) weeks.push(cells.slice(index, index + 7));
  return weeks;
}

export type DayTiming = "past" | "today" | "future";

export function dayTiming(dateISO: string, todayISO: string): DayTiming {
  if (dateISO === todayISO) return "today";
  return dateISO < todayISO ? "past" : "future";
}

/** A day with no record can be marked by HR unless it is still in the future. A day with a record opens its detail instead. */
export function canMark(day: DayRecord, todayISO: string): boolean {
  return day.record_id === null && dayTiming(day.date, todayISO) !== "future";
}

/** What a day should be shown as: its status, except that a day with no record is "Not marked" once it has happened and "Upcoming" before. */
export function effectiveStatus(day: Pick<DayRecord, "date" | "status">, todayISO: string): string {
  if (day.status !== "no_record") return day.status;
  return dayTiming(day.date, todayISO) === "future" ? "future" : "no_record";
}

export function countByStatus(days: DayRecord[], todayISO: string): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const day of days) {
    const status = effectiveStatus(day, todayISO);
    counts[status] = (counts[status] ?? 0) + 1;
  }
  return counts;
}

/** How long to draw the hours bar: a visual scale of 10 hours = full width, with no business meaning. */
export function hoursBarPercent(hours: number): number {
  return Math.max(0, Math.min(100, Math.round((hours / 10) * 100)));
}

export interface MonthInsights {
  /** Days up to today that were working days (not a week off or holiday). */
  workingDays: number;
  /** Present, late and half days. */
  worked: number;
  /** worked / workingDays as a whole percent, or null before there is a working day to measure. */
  attendancePercent: number | null;
  /** Total hours / days worked, one decimal, or null when no day was worked. */
  averageHours: number | null;
  /** Working days up to today with no attendance record at all (candidates to mark). */
  unrecorded: number;
}

const OFF_DAYS = new Set(["weekly_off", "holiday"]);
const WORKED = new Set(["present", "late", "half_day"]);

export function monthInsights(days: DayRecord[], todayISO: string): MonthInsights {
  const upToToday = days.filter(day => day.date <= todayISO);
  const working = upToToday.filter(day => !OFF_DAYS.has(day.status));
  const workedDays = working.filter(day => WORKED.has(day.status));
  const hours = workedDays.reduce((sum, day) => sum + (day.total_hours || 0), 0);
  return {
    workingDays: working.length,
    worked: workedDays.length,
    attendancePercent: working.length > 0 ? Math.round((workedDays.length / working.length) * 100) : null,
    averageHours: workedDays.length > 0 ? Math.round((hours / workedDays.length) * 10) / 10 : null,
    unrecorded: working.filter(day => day.record_id === null && day.status === "no_record").length,
  };
}

export interface BarSegment { status: string; count: number }

/** The coloured bar's segments: each status's share of the working days so far, plus the days with no record. */
export function barSegments(days: DayRecord[], todayISO: string): BarSegment[] {
  const working = days.filter(day => day.date <= todayISO && !OFF_DAYS.has(day.status));
  const counts = countByStatus(working, todayISO);
  return ["present", "late", "half_day", "on_leave", "incomplete", "absent", "no_record"]
    .map(status => ({ status, count: counts[status] ?? 0 }))
    .filter(segment => segment.count > 0);
}

/** "09:05 – 18:10", "09:05 – still in", or "" when there is no clock-in. */
export function timeRangeLabel(day: Pick<DayRecord, "clock_in" | "clock_out">): string {
  if (!day.clock_in) return "";
  return `${day.clock_in} – ${day.clock_out ?? "still in"}`;
}

/** The day shown in the side panel when nobody has picked one: today if it is in this month, else the latest day with a record, else the 1st. */
export function defaultSelectedDate(days: DayRecord[], todayISO: string): string | null {
  if (days.some(day => day.date === todayISO)) return todayISO;
  const recorded = days.filter(day => day.record_id !== null);
  return recorded.length > 0 ? recorded[recorded.length - 1].date : days[0]?.date ?? null;
}

/** One plain sentence about a day, for the side panel. `status` is the effective status (see effectiveStatus). */
export function daySentence(day: Pick<DayRecord, "total_hours">, status: string): string {
  const hours = day.total_hours > 0 ? ` ${day.total_hours}h worked.` : "";
  switch (status) {
    case "present": return day.total_hours > 0 ? `Present, ${day.total_hours}h worked.` : "Present.";
    case "late": return `Arrived late.${hours}`;
    case "half_day": return `Half day.${hours}`;
    case "on_leave": return "On approved leave.";
    case "absent": return "Marked absent.";
    case "incomplete": return "Clocked in but never clocked out.";
    case "weekly_off": return "Week off.";
    case "holiday": return "Public holiday.";
    case "no_record": return "Nothing is recorded for this day yet.";
    default: return "This day has not happened yet.";
  }
}

/** The employees matching what was typed. Every word typed must appear somewhere in the name, ID, department or designation (any case). */
export function filterEmployees(employees: EmployeeOption[], query: string): EmployeeOption[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return employees;
  return employees.filter(employee => {
    const haystack = `${employee.full_name} ${employee.employee_id} ${employee.department} ${employee.designation}`.toLowerCase();
    return words.every(word => haystack.includes(word));
  });
}
