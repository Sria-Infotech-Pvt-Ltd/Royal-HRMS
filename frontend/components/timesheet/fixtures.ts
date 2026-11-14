// Test data for the timesheet screens (not shipped UI): a full week view the API would send, easy to tweak per test.

import type { TimesheetDay, TimesheetDayStatus, TimesheetLine, TimesheetWeekView } from "@/types/timesheet";

export const WEEK = "2026-11-09";
export const DATES = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function day(index: number, over: Partial<TimesheetDay> = {}): TimesheetDay {
  const status: TimesheetDayStatus = index >= 5 ? "weekly_off" : "present";
  return {
    date: DATES[index], weekday: WEEKDAYS[index], status, status_label: status, holiday_name: "", is_future: false,
    is_employed: true, attendance_minutes: 0, ...over,
  };
}

export function line(over: Partial<TimesheetLine> = {}): TimesheetLine {
  return {
    id: "L1", assignment_id: 1, project_id: 10, project_code: "P1", project_name: "Alpha", is_internal: false, is_billable: false,
    entries: {}, ...over,
  };
}

export function internalLine(over: Partial<TimesheetLine> = {}): TimesheetLine {
  return line({ id: "L2", assignment_id: null, project_id: null, project_code: "", project_name: "Internal / Non-project work", is_internal: true, ...over });
}

export function weekView(over: Partial<TimesheetWeekView> = {}): TimesheetWeekView {
  return {
    id: "T1", employee: { id: "U1", name: "Asha Rao", employee_id: "E001" }, week_start: WEEK, week_end: "2026-11-15", due_date: "2026-11-13",
    status: "draft", is_editable: true, is_late: false, return_reason: "", submitted_at: null, decided_at: null, approver: null, decided_by: null,
    days: DATES.map((_, index) => day(index)), lines: [line(), internalLine()],
    totals: { daily: {}, week: "0.00", billable: "0.00", non_billable: "0.00", target: "40.00", attendance_hours: "0.00" },
    limits: { daily_warning_hours: "12.00", daily_max_hours: "24.00", hour_step: "0.25", weekly_target_hours: "40.00", max_note_length: 500 },
    events: [], ...over,
  };
}
