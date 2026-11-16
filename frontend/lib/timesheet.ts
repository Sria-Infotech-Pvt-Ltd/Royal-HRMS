// Pure helpers for the weekly timesheet screens: hour parsing, totals, week dates, status labels, and turning the grid
// back into the save request. No React and no network, so every rule here is unit-tested on its own.

import type { StatusPillTone } from "@/components/employees/StatusPill";
import type {
  GridLine, TimesheetDay, TimesheetLine, TimesheetSavePayload, TimesheetStatus, WeeklyTimesheetSummary,
} from "@/types/timesheet";

export const HOUR_STEP = 0.25;
export const MAX_DAILY_HOURS = 24;
export const DAILY_WARNING_HOURS = 12;

const HOURS_PATTERN = /^\d{1,2}(\.\d{1,2})?$/;

// ── Hours ──────────────────────────────────────────────────────────────────────────────────────────────────────────

/** The number of hours typed in a cell, or null when it is not a valid quarter-hour amount from 0 to 24. Empty means 0. */
export function parseHoursText(text: string): number | null {
  const trimmed = text.trim();
  if (trimmed === "") return 0;
  if (!HOURS_PATTERN.test(trimmed)) return null;
  const value = Number(trimmed);
  if (value > MAX_DAILY_HOURS) return null;
  return Math.round(value * 100) % (HOUR_STEP * 100) === 0 ? value : null;
}

export function isValidHoursText(text: string): boolean {
  return parseHoursText(text) !== null;
}

/** Hours for totals: an invalid cell counts as 0 (the screen marks it and refuses to save until it is fixed). */
export function cellHours(text: string): number {
  return parseHoursText(text) ?? 0;
}

/** 8 -> "8", 7.5 -> "7.5", 7.25 -> "7.25": no trailing zeros, for display. */
export function formatHours(value: number): string {
  return String(Number(value.toFixed(2)));
}

export function toGridLines(lines: TimesheetLine[]): GridLine[] {
  return lines.map((line, index) => ({
    key: line.id ?? `new-${line.is_internal ? "internal" : line.assignment_id ?? index}`,
    assignment_id: line.assignment_id,
    project_name: line.project_name,
    project_code: line.project_code,
    is_internal: line.is_internal,
    is_billable: line.is_billable,
    cells: Object.fromEntries(
      Object.entries(line.entries).map(([date, cell]) => [date, { hours: cell.hours === "0.00" ? "" : formatHours(Number(cell.hours)), note: cell.note }]),
    ),
  }));
}

export function toSavePayload(lines: GridLine[]): TimesheetSavePayload {
  return {
    lines: lines.map(line => ({
      assignment_id: line.assignment_id,
      is_internal: line.is_internal,
      is_billable: line.is_billable,
      entries: Object.entries(line.cells)
        .filter(([, cell]) => cellHours(cell.hours) > 0 || cell.note.trim() !== "")
        .map(([date, cell]) => ({ date, hours: cellHours(cell.hours).toFixed(2), note: cell.note.trim() }))
        .sort((first, second) => first.date.localeCompare(second.date)),
    })),
  };
}

export function hasInvalidCells(lines: GridLine[]): boolean {
  return lines.some(line => Object.values(line.cells).some(cell => !isValidHoursText(cell.hours)));
}

/** True when the grid differs from what is saved (compared as the request that would be sent). */
export function isDirty(current: GridLine[], saved: GridLine[]): boolean {
  return JSON.stringify(toSavePayload(current)) !== JSON.stringify(toSavePayload(saved));
}

export function dailyTotals(lines: GridLine[], dates: string[]): Record<string, number> {
  const totals: Record<string, number> = Object.fromEntries(dates.map(date => [date, 0]));
  for (const line of lines) {
    for (const date of dates) totals[date] += cellHours(line.cells[date]?.hours ?? "");
  }
  return totals;
}

export function lineTotal(line: GridLine, dates: string[]): number {
  return dates.reduce((sum, date) => sum + cellHours(line.cells[date]?.hours ?? ""), 0);
}

export function weekTotal(lines: GridLine[], dates: string[]): number {
  return lines.reduce((sum, line) => sum + lineTotal(line, dates), 0);
}

export function billableTotal(lines: GridLine[], dates: string[]): number {
  return lines.filter(line => line.is_billable).reduce((sum, line) => sum + lineTotal(line, dates), 0);
}

// ── Week dates (noon avoids any daylight-saving edge) ───────────────────────────────────────────────────────────────

function atNoon(iso: string): Date {
  return new Date(`${iso}T12:00:00`);
}

export function toIso(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function addDays(iso: string, days: number): string {
  const date = atNoon(iso);
  date.setDate(date.getDate() + days);
  return toIso(date);
}

export function mondayOf(iso: string): string {
  const date = atNoon(iso);
  return addDays(iso, -((date.getDay() + 6) % 7));
}

export function currentMonday(now: Date = new Date()): string {
  return mondayOf(toIso(now));
}

export function isIsoDate(value: string | null | undefined): value is string {
  return !!value && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(atNoon(value).getTime());
}

export function weekRangeLabel(startIso: string, endIso: string): string {
  const start = atNoon(startIso);
  const end = atNoon(endIso);
  const month = (date: Date) => date.toLocaleDateString("en-GB", { month: "short" });
  const sameMonth = start.getMonth() === end.getMonth();
  return `${start.getDate()}${sameMonth ? "" : ` ${month(start)}`} – ${end.getDate()} ${month(end)} ${end.getFullYear()}`;
}

export function dayNumber(iso: string): number {
  return atNoon(iso).getDate();
}

// ── Status wording ─────────────────────────────────────────────────────────────────────────────────────────────────

export const STATUS_LABEL: Record<TimesheetStatus, string> = {
  draft: "Draft", submitted: "Submitted", returned: "Returned", approved: "Approved",
};

export const STATUS_TONE: Record<TimesheetStatus, StatusPillTone> = {
  draft: "neutral", submitted: "warn", returned: "error", approved: "success",
};

/** The button on the Attendance and Home cards, from the state of this week's sheet (null = nothing saved yet). */
export function cardActionLabel(status: TimesheetStatus | null): string {
  if (status === "draft") return "Continue timesheet";
  if (status === "returned") return "Fix and resubmit";
  if (status === "submitted" || status === "approved") return "View timesheet";
  return "Fill timesheet";
}

/** "FRI": the weekday the week's timesheet is due (Monday + 4). */
export function dueDayLabel(weekStartIso: string): string {
  return atNoon(addDays(weekStartIso, 4)).toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
}

export interface CardState {
  subtitle: string;
  badge: string;
  /** The badge colour class used by the Home card ("badge-success" | "badge-warn" | "badge-error"). */
  badgeClass: "badge-success" | "badge-warn" | "badge-error";
  /** True once nothing is left for the employee to do this week. */
  isDone: boolean;
}

/** What the Home and Attendance cards say about this week, from the real timesheet's state (and the old tick-box). */
export function timesheetCardState(summary: WeeklyTimesheetSummary, dueDay: string): CardState {
  const status = summary.timesheet_status;
  if (status === "approved") return { subtitle: "Approved. This week is locked.", badge: "APPROVED", badgeClass: "badge-success", isDone: true };
  if (status === "submitted") return { subtitle: "Submitted. Waiting for approval.", badge: "SUBMITTED", badgeClass: "badge-success", isDone: true };
  if (status === "returned") return { subtitle: "Sent back by your approver. Fix the hours and resubmit.", badge: "RETURNED", badgeClass: "badge-error", isDone: false };
  if (summary.submitted) return { subtitle: "Submitted. Thank you.", badge: "SUBMITTED", badgeClass: "badge-success", isDone: true };
  const remaining = Math.max(0, summary.target_hours - summary.hours_logged);
  const subtitle = remaining > 0
    ? `${remaining} hour${remaining === 1 ? "" : "s"} remaining. Enter your hours per project, then submit.`
    : "Target reached. Ready to submit.";
  return { subtitle, badge: `DUE ${dueDay}`, badgeClass: "badge-warn", isDone: false };
}

/** A short chip for days that are not ordinary working days; null for a normal day. */
export function dayChipLabel(day: TimesheetDay): string | null {
  if (day.status === "holiday") return day.holiday_name || "Holiday";
  if (day.status === "weekly_off") return "Weekly off";
  if (day.status === "on_leave") return "On leave";
  if (day.status === "not_employed") return "Not employed";
  return null;
}

// ── Server errors ──────────────────────────────────────────────────────────────────────────────────────────────────

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Every problem the server listed for a rejected save or submit (envelope data.errors), or its single message. */
export function problemsFromError(error: unknown, fallback: string): string[] {
  const body = isRecord(error) && isRecord(error.response) && isRecord(error.response.data) ? error.response.data : null;
  const data = body && isRecord(body.data) ? body.data : null;
  const listed = data && Array.isArray(data.errors) ? data.errors.filter((item): item is string => typeof item === "string") : [];
  if (listed.length > 0) return listed;
  return [body && typeof body.message === "string" ? body.message : fallback];
}
