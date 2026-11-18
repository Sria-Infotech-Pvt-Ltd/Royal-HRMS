// Pure helpers for the Attendance tab's table and filters. No React.

import type { SummaryChips } from "@/types/attendance";
import { PALETTE } from "./attendancePalette";

export interface StatusTab { key: "" | keyof SummaryChips; label: string; colour: string }

/** The status filter tabs, in reading order. "All" clears the filter. */
export const STATUS_TABS: readonly StatusTab[] = [
  { key: "", label: "All", colour: "var(--on-variant)" },
  { key: "present", label: "Present", colour: PALETTE.present },
  { key: "late", label: "Late", colour: PALETTE.late },
  { key: "absent", label: "Absent", colour: PALETTE.absent },
  { key: "on_leave", label: "On Leave", colour: PALETTE.on_leave },
  { key: "half_day", label: "Half Day", colour: PALETTE.half_day },
  { key: "weekly_off", label: "Weekly Off", colour: PALETTE.weekly_off },
];

/** The number to show on a tab, or null for "All" (no count: the chips leave out holidays and incomplete days, so a sum could mislead). */
export function tabCount(key: StatusTab["key"], chips: SummaryChips | undefined): number | null {
  if (key === "") return null;
  return chips?.[key] ?? 0;
}

export type SortKey = "name" | "clock_in" | "status";
export interface SortState { by: SortKey; dir: "asc" | "desc" }

/** Clicking the column that is already sorted flips the direction; clicking another column sorts it ascending. */
export function nextSort(current: SortState, key: SortKey): SortState {
  if (current.by === key) return { by: key, dir: current.dir === "asc" ? "desc" : "asc" };
  return { by: key, dir: "asc" };
}

export interface TimeSummary { kind: "none" | "partial" | "full"; clockIn: string; clockOut: string }

const MISSING = "—";

/** What the Time cell shows: nothing recorded, only a clock-in so far, or both. The API sends "—" for a missing time. */
export function summariseTimes(clockIn: string, clockOut: string): TimeSummary {
  const hasIn = clockIn !== MISSING && clockIn.trim() !== "";
  const hasOut = clockOut !== MISSING && clockOut.trim() !== "";
  if (!hasIn && !hasOut) return { kind: "none", clockIn: "", clockOut: "" };
  return { kind: hasIn && hasOut ? "full" : "partial", clockIn: hasIn ? clockIn : MISSING, clockOut: hasOut ? clockOut : MISSING };
}

/** Whether the API value means "nothing" (it sends "—"). */
export const isBlank = (value: string): boolean => value === MISSING || value.trim() === "";
