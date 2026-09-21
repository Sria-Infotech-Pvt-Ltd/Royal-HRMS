export interface DashboardKPIs {
  total_employees:      number;
  pending_approvals:    number;
  employees_onboarding: number;
  active_branches:      number;
  api_status:           string | boolean;
  database_status:      string | boolean;
  mail_status:          string | boolean;
  storage_status:       string | boolean;
}

export interface PendingApprovals {
  leave_requests:      number;
  expense_claims:      number;
  onboarding_reviews:  number;
  separation_requests: number;
  total_pending:       number;
}

export interface DeptHeadcount {
  department: string;
  count:      number;
}

export interface LifecycleEmployee {
  // identity — API may use any of these
  id?:               string;
  employee_id?:      string;
  name?:             string;
  full_name?:        string;
  employee_name?:    string;
  designation?:      string;
  department?:       string;
  // new joiners
  join_date?:        string;
  joining_date?:     string;
  // notice period
  last_working_day?: string;
  last_day?:         string;
  days_left?:        number;
  // work anniversaries
  years?:            number;
  anniversary_date?: string;
  date?:             string;
}

export interface LifecycleGroup {
  count:     number;
  employees: LifecycleEmployee[];
}

export interface EmployeeLifecycle {
  new_joiners:        LifecycleGroup;
  notice_period:      LifecycleGroup;
  work_anniversaries: LifecycleGroup;
}

export interface AnnouncementData {
  id:          string | number;
  title:       string;
  body?:       string;
  content?:    string;
  category?:   string;
  created_at?: string;
  posted_on?:  string;
  author?:     string;
  created_by?: string | { name: string };
}

export interface AuditLogEntry {
  id:          string | number;
  action:      string;
  module:      string;
  subject:     string;
  actor?:      string;
  actor_name?: string;
  ip?:         string;
  ip_address?: string;
  timestamp:   string;
  created_at?: string;
}

export interface AuditLogsResponse {
  count:   number;
  results: AuditLogEntry[];
}

// ── HR Dashboard ───────────────────────────────────────────────────────────────

export interface HRTodayAttendance {
  status:                string;
  first_punch_in:        string | null;
  last_punch_out:        string | null;
  total_working_minutes: number;
}

export interface HRKPIs {
  total_workforce:               number;
  pending_actions:               number;
  active_interviews:             number;
  employees_on_probation:        number;
  clocked_in:                    boolean;
  today_attendance:              HRTodayAttendance | null;
  attendance_correction_pending: number;
}

export interface HRActionQueue {
  total_pending:          number;
  candidate_reviews:      number;
  leave_approvals:        number;
  attendance_corrections: number;
  expense_claims:         number;
  onboarding_reviews:     number;
  separation_requests:    number;
}

export interface LeaveUpdatePayload {
  action_queue:    HRActionQueue | null;
  pending_actions: number | null;
}

export interface RecruitmentFunnel {
  interviews_scheduled: number;
  interviewed:          number;
  selected:             number;
  details_submitted:    number;
  onboarded:            number;
}

export interface AttendanceSummary {
  present:    number;
  absent:     number;
  late:       number;
  leave:      number;
  weekly_off: number;
  holiday:    number;
}

export interface HRLifecycleEmployee {
  employee_id:      string;
  full_name:        string;
  department:       string;
  designation?:     string;
  date_of_joining?: string;
  years_completed?: number;
  anniversary_date?: string;
}

export interface HREmployeeLifecycle {
  new_joiners:        { count: number; employees: HRLifecycleEmployee[] };
  notice_period:      { count: number; employees: HRLifecycleEmployee[] };
  work_anniversaries: { count: number; employees: HRLifecycleEmployee[] };
}

export interface AttendancePunch {
  type:                "IN" | "OUT";
  time:                string;
  location:            string;
  attendance_mode:     string;
  is_inside_geofence:  boolean;
  calculated_distance: number;
}

export interface AttendanceToday {
  is_clocked_in:   boolean;
  punches:         AttendancePunch[];
  total_seconds:   number;
  session_seconds: number;
  date_display:    string;
}

export interface HRBirthdayEmployee {
  employee_id:   string;
  full_name:     string;
  email?:        string;
  department:    string;
  branch?:       string;
  date_of_birth: string;
  days_until:    number;
}

// ── Workforce Dashboard overview (Screen 1) ────────────────────────────────────
// Backed by HRDashboardOverviewView / HRLifecycleActionRegisterView
// (backend/apps/dashboard/views/overview.py) — every field a real computed
// number, never a fabricated demo value.

export interface WeeklyAttendanceDay {
  label: string;
  count: number;
}

export interface DashboardOverview {
  total_headcount: number;
  new_this_month: number;
  present_today: number;
  attendance_pct: number;
  payroll_ready: number;
  payroll_total: number;
  payroll_blocked: number;
  onboarding_in_progress: number;
  joining_this_week: number;
  attendance_exceptions_today: number;
  open_requests: number;
  compliance_pct: number;
  weekly_attendance: WeeklyAttendanceDay[];
}

export type LifecycleActionState = "Pending" | "In Progress";

export interface LifecycleActionRow {
  case_ref: string;
  employee_name: string;
  action: string;
  effective: string;
  owner: string;
  state: LifecycleActionState;
  link: string;
}
