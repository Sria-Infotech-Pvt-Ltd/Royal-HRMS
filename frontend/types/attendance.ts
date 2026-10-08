export interface PunchEntry {
  type:                "IN" | "OUT";
  time:                string;
  location:            string;
  attendance_mode:     string;
  is_inside_geofence:  boolean | null;
  calculated_distance: number | null;
}

export interface TodaySession {
  is_clocked_in:   boolean;
  day_completed:   boolean;
  punches:         PunchEntry[];
  total_seconds:   number;
  session_seconds: number;
  date_display:    string;
}

export interface AttendanceStats {
  days_present:          number;
  late_arrivals:         number;
  lop_pending:           number;
  avg_hours_per_day:     number;
  attendance_percentage: number;
  working_days:          number;
}

export interface MonthlySummary {
  working_days: number;
  days_present: number;
  days_absent:  number;
  leave_days:   number;
  half_days:    number;
  ot_hours:     string;
}

export interface DayRecord {
  date:                    string;
  status:                  string;       // display string from backend: "Present", "Holiday", etc.
  color:                   string;       // hex color supplied by backend
  clockIn:                 string | null;
  clockOut:                string | null;
  hours:                   string | null;
  note:                    string | null;
  holiday_name?:           string | null;
  canRegularize:           boolean;
  regularization_required: boolean;
}

export interface CalendarResponse {
  calendar: { days: Record<string, DayRecord> };
  history:  HistoryRow[];
  month:    number;
  year:     number;
}

export interface HistoryRow {
  date:          string;
  day:           string;
  clockIn:       string | null;
  clockOut:      string | null;
  hours:         string | null;
  status:        string;
  canRegularize: boolean;
}

export type PunchType       = "IN" | "OUT" | "BOTH";
export type CorrectionReason = "biometric_error" | "forgot_to_punch" | "field_work" | "system_downtime" | "other";
export type AttendanceMode   = "office" | "wfh" | "field" | "client_location" | "remote_office";

// GPS reading captured by useClockWidget.prepareLocation, already validated
// against the employee's geofence via the /attendance/geofence-check/
// endpoint before a face verification modal is ever shown.
export interface PunchLocation {
  latitude:  number;
  longitude: number;
  accuracy:  number;
}

// ── HR Management ──────────────────────────────────────────────────────────

export interface StatCards {
  present_today:   number;
  absent:          number;
  late_arrivals:   number;
  on_leave:        number;
  total_employees: number;
}

export interface SummaryChips {
  present:    number;
  late:       number;
  absent:     number;
  on_leave:   number;
  half_day:   number;
  weekly_off: number;
  holiday:    number;
}

export interface TabBadges {
  invalid_punches: number;
  un_punches:      number;
}

export interface DashboardData {
  stat_cards:    StatCards;
  summary_chips: SummaryChips;
  tab_badges:    TabBadges;
}

export interface AttendanceRow {
  record_id:   string | null;
  employee_id: string;
  name:        string;
  initials:    string;
  department:  string;
  branch:      string;
  clock_in:    string;   // "09:05" or "—"
  clock_out:   string;
  total_hours: string;   // "9h 10m" or "—"
  ot:          string;   // "10m" or "—"
  status:      string;   // "Present", "Late", etc.
  status_key:  string;   // "present", "late", etc.
  is_late:     boolean;
}

export interface PaginatedResponse<T> {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     T[];
}

export type PaginatedAttendance     = PaginatedResponse<AttendanceRow>;
export type PaginatedOvertime       = PaginatedResponse<OvertimeRow>;
export type PaginatedInvalidPunches = PaginatedResponse<InvalidPunch>;
export type PaginatedUnpunches      = PaginatedResponse<UnpunchRow>;

// Punch line item shown in the attendance detail drawer timeline.
// Distinct from `PunchEntry` above, which describes a live clock-in/out session.
export interface AttendanceDetailPunch {
  punch_type:  string;
  time:        string;
  source:      string;
  mode:        string;
  is_geofence: boolean | null;
  distance_m:  number | null;
}

export interface AttendanceDetail {
  record_id:     string;
  employee_id:   string;
  name:          string;
  department:    string;
  branch:        string;
  date:          string;
  status:        string;
  status_key:    string;
  clock_in:      string;
  clock_out:     string;
  clock_in_latitude:   number | null;
  clock_in_longitude:  number | null;
  clock_in_location_label:  string | null;
  clock_out_latitude:  number | null;
  clock_out_longitude: number | null;
  clock_out_location_label: string | null;
  total_hours:   string;
  overtime:      string;
  is_late:       boolean;
  is_early_exit: boolean;
  note:          string;
  punches:       AttendanceDetailPunch[];
}

export interface OvertimeRow {
  id:          string;
  employee_id: string;
  name:        string;
  initials:    string;
  date:        string;
  ot_hours:    string;
  ot_type:     string;
  ot_amount:   string;
  approved_by: string;
  status:      string;
}

export interface InvalidPunch {
  id:              string;
  device_id:       string;
  raw_time:        string;
  biometric_id:    string;
  issue:           string;
  issue_type:      "duplicate" | "future" | "no-match";
  suggested_match: string;
  branch:          string;
}

export interface AttendanceAuditEntry {
  event:        string;
  performed_by: string;
  performed_at: string;
  old_value:    string;
  new_value:    string;
  action:       string;
  remarks:      string;
}

export interface InvalidPunchAssignPayload {
  assigned_to: string;
}

export interface InvalidPunchDiscardPayload {
  remarks: string;
}

export interface InvalidPunchConvertPayload {
  target_punch_type: "IN" | "OUT";
  target_time:        string;
}

export interface UnpunchRow {
  employee_id:         string;
  name:                string;
  initials:            string;
  date:                string;
  clock_in:            string;
  expected_out:        string;
  branch:              string;
  correction_pending:  boolean;
  correction_id:       string | null;
}

export type CorrectionStatus = "pending" | "l2_pending" | "approved" | "rejected";
export type CorrectionStageStatus = "approved" | "rejected" | null;

export interface CorrectionRow {
  id:               string;
  employee_id:      string;
  name:             string;
  department:       string;
  branch:           string;
  date:             string;
  punch_type:       PunchType;
  requested_in:     string | null;
  requested_out:    string | null;
  reason:           string;
  status:           CorrectionStatus;
  // L1 (manager) stage
  l1_approver_name: string | null;
  l1_status:        CorrectionStageStatus;
  l1_remarks:       string;
  // L2 (HR) stage
  l2_approver_name: string | null;
  l2_status:        CorrectionStageStatus;
  l2_remarks:       string;
  // True when the current user is the designated approver for whichever
  // stage this request currently sits at — drives whether Approve/Reject
  // render as functional buttons or read-only status.
  can_action:       boolean;
  reviewed_by:      string | null;
  reviewed_at:      string | null;
}

export type PaginatedCorrections = PaginatedResponse<CorrectionRow>;

export type CorrectionReviewAction = "approve" | "reject";

export interface OvertimeCreatePayload {
  employee_id:  string;
  date:         string;   // YYYY-MM-DD
  ot_type:      "regular" | "holiday" | "weekly_off";
  ot_start:     string;   // HH:MM
  ot_end:       string;   // HH:MM
  approved_by?: string;
  reason?:      string;
}

export interface ImportRowError {
  row:             number;
  employee_id:     string;
  employee_name:   string;
  attendance_date: string;
  reason:          string;
  resolution:      string;
}

export interface ImportResult {
  import_id:          string;
  status:             "success" | "partial_success" | "failed";
  message:            string;
  total_records:      number;
  successful:         number;
  failed:             number;
  skipped:            number;
  errors:             ImportRowError[];
  error_report_csv:   string;
  first_imported_date?: string | null; // ISO date of earliest successfully imported record
}
