// Pure helpers for the Attendance Detail panel: the plain-words banners, labels and colours. No React.

import type { CorrectionStatus, PunchType } from "@/types/attendance";
import { PALETTE, statusColour } from "./attendancePalette";
import { relativeDayLabel, weekdayName } from "./attendanceDates";

export const PUNCH_TYPE_LABEL: Record<PunchType, string> = { IN: "Clock In", OUT: "Clock Out", BOTH: "Both IN & OUT" };

export const CORRECTION_STATUS: Record<CorrectionStatus, { label: string; colour: string }> = {
  pending: { label: "Pending", colour: PALETTE.late },
  l2_pending: { label: "Waiting for HR", colour: PALETTE.half_day },
  approved: { label: "Approved", colour: PALETTE.present },
  rejected: { label: "Rejected", colour: PALETTE.absent },
};

const AUDIT_EVENT_COLOUR: Record<string, string> = {
  CLOCK_IN: PALETTE.present, CLOCK_OUT: PALETTE.half_day, CORRECTION_REQUESTED: PALETTE.late, CORRECTION_APPROVED: PALETTE.present,
  CORRECTION_REJECTED: PALETTE.absent, IMPORTED: PALETTE.on_leave, EDITED: PALETTE.late, RECALCULATED: PALETTE.half_day,
  INVALID_PUNCH_ASSIGNED: PALETTE.on_leave, INVALID_PUNCH_DISCARDED: PALETTE.absent, INVALID_PUNCH_CONVERTED: PALETTE.present,
};

export const auditEventColour = (event: string): string => AUDIT_EVENT_COLOUR[event] ?? PALETTE.weekly_off;

/** "CORRECTION_REQUESTED" -> "Correction Requested". */
export function formatEventLabel(event: string): string {
  return event.split("_").map(word => word.charAt(0) + word.slice(1).toLowerCase()).join(" ");
}

/** "Tuesday, 17 November 2026". */
export function longDate(dateISO: string): string {
  const [year, month, day] = dateISO.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

/** "Yesterday", "4 days ago" ... for the line under the date. */
export const dateCaption = (dateISO: string, todayISO: string): string => `${weekdayName(dateISO)} · ${relativeDayLabel(dateISO, todayISO)}`;

export interface Banner { key: string; colour: string; icon: string; title: string; hint: string }

interface BannerInput {
  status_key: string;
  clock_in: string;
  clock_out: string;
  punches: unknown[];
  is_late: boolean;
  is_early_exit: boolean;
}

const BLANK = new Set(["", "—", "–", "-"]);
const NO_ATTENDANCE_EXPECTED: Record<string, { title: string; icon: string }> = {
  on_leave: { title: "On approved leave", icon: "ti-plane" },
  weekly_off: { title: "Week off", icon: "ti-moon" },
  holiday: { title: "Public holiday", icon: "ti-confetti" },
};

/** The short coloured messages shown above the times: what is unusual about this day, in plain words. */
export function detailBanners(day: BannerInput): Banner[] {
  const off = NO_ATTENDANCE_EXPECTED[day.status_key];
  if (off) return [{ key: day.status_key, colour: statusColour(day.status_key), icon: off.icon, title: off.title, hint: "No attendance is expected on this day." }];

  const banners: Banner[] = [];
  const noPunches = day.punches.length === 0 && BLANK.has(day.clock_in) && BLANK.has(day.clock_out);
  if (noPunches) {
    const absent = day.status_key === "absent";
    banners.push({
      key: "no-punch", colour: absent ? PALETTE.absent : PALETTE.not_marked, icon: "ti-fingerprint-off", title: "No punch recorded",
      hint: absent ? "No clock-in or clock-out was captured. If they did work, use Edit to record it." : "Nothing is recorded for this day yet.",
    });
  }
  if (day.status_key === "incomplete") {
    banners.push({ key: "incomplete", colour: PALETTE.incomplete, icon: "ti-clock-question", title: "Clocked in but never clocked out", hint: "Add the missing clock-out with Edit, or approve a correction request." });
  }
  if (day.is_late) banners.push({ key: "late", colour: PALETTE.late, icon: "ti-clock-exclamation", title: "Arrived late", hint: "The clock-in was after the grace time." });
  if (day.is_early_exit) banners.push({ key: "early", colour: PALETTE.late, icon: "ti-door-exit", title: "Left early", hint: "The clock-out was before the end of the shift." });
  return banners;
}
