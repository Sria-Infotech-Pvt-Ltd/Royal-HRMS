// Pure helpers for the OT Entry tab: the overtime types, the live duration, the form check and the colours of the records table. No React.

import type { OvertimeCreatePayload } from "@/types/attendance";
import { PALETTE } from "./attendancePalette";

export interface OtTypeOption { value: OvertimeCreatePayload["ot_type"]; label: string; multiplier: string; icon: string; colour: string; hint: string }

/** The three overtime types the server accepts, with the rate each is paid at (the same figures the old drop-down showed). */
export const OT_TYPES: readonly OtTypeOption[] = [
  { value: "regular", label: "Regular", multiplier: "1.5×", icon: "ti-clock-plus", colour: PALETTE.half_day, hint: "Extra hours on a normal working day" },
  { value: "holiday", label: "Holiday", multiplier: "2.0×", icon: "ti-confetti", colour: PALETTE.holiday, hint: "Worked on a public holiday" },
  { value: "weekly_off", label: "Weekly Off", multiplier: "1.5×", icon: "ti-moon", colour: PALETTE.on_leave, hint: "Worked on a week off" },
];

/** Minutes from "HH:MM" start to "HH:MM" end, or null when either time is missing or the end is not after the start. */
export function minutesBetween(start: string, end: string): number | null {
  const toMinutes = (value: string) => {
    const match = /^(\d{1,2}):(\d{2})$/.exec(value);
    return match ? Number(match[1]) * 60 + Number(match[2]) : null;
  };
  const from = toMinutes(start);
  const to = toMinutes(end);
  if (from === null || to === null || to <= from) return null;
  return to - from;
}

/** 120 -> "2h 00m", 45 -> "45m", 90 -> "1h 30m". */
export function durationLabel(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest}m`;
  return `${hours}h ${String(rest).padStart(2, "0")}m`;
}

/** The message for the first thing wrong with the form, or null when it can be sent. The wording is the form's long-standing wording. */
export function validateOtForm(form: Pick<OvertimeCreatePayload, "employee_id" | "date" | "ot_start" | "ot_end">): string | null {
  if (!form.employee_id) return "Please select an employee.";
  if (!form.date) return "Please select a date.";
  if (form.ot_end <= form.ot_start) return "OT end time must be after OT start time.";
  return null;
}

/** The colour of a record's status pill: approved green, rejected red, pending orange, anything else slate. */
export function otStatusColour(status: string): string {
  const key = status.trim().toLowerCase();
  if (key === "approved") return PALETTE.present;
  if (key === "rejected") return PALETTE.absent;
  if (key === "pending") return PALETTE.late;
  return PALETTE.not_marked;
}

/** The colour of a record's type pill, from the display text the server sends ("Regular", "Holiday", "Weekly Off" ...). */
export function otTypeColour(typeLabel: string): string {
  const key = typeLabel.toLowerCase();
  if (key.includes("holiday")) return PALETTE.holiday;
  if (key.includes("week")) return PALETTE.on_leave;
  return PALETTE.half_day;
}
