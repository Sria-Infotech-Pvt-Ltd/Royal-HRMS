// Shapes of the weekly timesheet API (/attendance/timesheets/). Hours travel as decimal strings ("7.50") so no float
// rounding ever reaches the server; the screen converts to numbers only for display and live totals.

export type TimesheetStatus = "draft" | "submitted" | "returned" | "approved";

export type TimesheetDayStatus =
  | "present" | "late" | "absent" | "half_day" | "weekly_off" | "holiday" | "on_leave" | "incomplete" | "not_employed" | "upcoming";

export interface TimesheetPerson {
  id: string;
  name: string;
  employee_id: string;
}

export interface TimesheetDay {
  date: string;
  weekday: string;
  status: TimesheetDayStatus;
  status_label: string;
  holiday_name: string;
  is_future: boolean;
  is_employed: boolean;
  attendance_minutes: number;
}

export interface TimesheetCell {
  hours: string;
  note: string;
}

export interface TimesheetLine {
  id: string | null;
  assignment_id: number | null;
  project_id: number | null;
  project_code: string;
  project_name: string;
  is_internal: boolean;
  is_billable: boolean;
  entries: Record<string, TimesheetCell>;
}

export interface TimesheetTotals {
  daily: Record<string, string>;
  week: string;
  billable: string;
  non_billable: string;
  target: string;
  attendance_hours: string;
}

export interface TimesheetLimits {
  daily_warning_hours: string;
  daily_max_hours: string;
  hour_step: string;
  weekly_target_hours: string;
  max_note_length: number;
}

export interface TimesheetEvent {
  id: string;
  event_type: "submitted" | "resubmitted" | "returned" | "approved" | "unlocked";
  from_status: string;
  to_status: string;
  reason: string;
  actor: TimesheetPerson | null;
  at: string;
}

export interface TimesheetWarning {
  code: "non_working_day" | "long_day";
  date: string;
  message: string;
}

export interface TimesheetIssues {
  errors: string[];
  warnings: TimesheetWarning[];
}

export interface TimesheetWeekView {
  id: string | null;
  employee: TimesheetPerson | null;
  week_start: string;
  week_end: string;
  due_date: string;
  status: TimesheetStatus;
  is_editable: boolean;
  is_late: boolean;
  return_reason: string;
  submitted_at: string | null;
  decided_at: string | null;
  approver: TimesheetPerson | null;
  decided_by: TimesheetPerson | null;
  days: TimesheetDay[];
  lines: TimesheetLine[];
  totals: TimesheetTotals;
  limits: TimesheetLimits;
  events: TimesheetEvent[];
  /** Present on the answer to a save or submit only. */
  issues?: TimesheetIssues;
  /** Present on a sheet opened from the approver's side. */
  can_decide?: boolean;
  can_unlock?: boolean;
}

export interface TimesheetRow {
  id: string;
  employee: TimesheetPerson;
  week_start: string;
  week_end: string;
  status: TimesheetStatus;
  is_late: boolean;
  total_hours: string;
  billable_hours: string;
  attendance_hours: string;
  submitted_at: string | null;
  decided_at: string | null;
  approver: string | null;
  return_reason: string;
  can_decide: boolean;
}

export interface TimesheetTeamPage {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: TimesheetRow[];
  pending_count: number;
}

/** The answer of the original /attendance/my-weekly-timesheet/ endpoint, which still feeds the Home and Attendance cards. */
export interface WeeklyTimesheetSummary {
  hours_logged: number;
  target_hours: number;
  week_start: string;
  week_end: string;
  submitted: boolean;
  submitted_at: string | null;
  /** The real timesheet's state for this week; null when nothing has been saved yet. */
  timesheet_status: TimesheetStatus | null;
}

/** What the grid edits: one row per project (or the Internal row), each day's hours kept as the text the person typed. */
export interface GridLine {
  key: string;
  assignment_id: number | null;
  project_name: string;
  project_code: string;
  is_internal: boolean;
  is_billable: boolean;
  cells: Record<string, TimesheetCell>;
}

export interface TimesheetSavePayload {
  lines: {
    assignment_id: number | null;
    is_internal: boolean;
    is_billable: boolean;
    entries: { date: string; hours: string; note: string }[];
  }[];
}
