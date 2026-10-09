import type { NoticeStatus } from "@/lib/noticePeriod";

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
  branch?:           string;
  approved_at?:      string | null;
  days_remaining?:   number;
  notice_status?:    NoticeStatus;
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

export interface NoticePeriodEmployee {
  employee_id:      string;
  full_name:        string;
  department:       string;
  branch:           string;
  request_id:       string;
  approved_at:      string | null;
  last_working_day: string;
  days_remaining:   number;
  notice_status:    NoticeStatus;
}

export interface HREmployeeLifecycle {
  new_joiners:        { count: number; employees: HRLifecycleEmployee[] };
  notice_period:      { count: number; employees: NoticePeriodEmployee[] };
  work_anniversaries: { count: number; employees: HRLifecycleEmployee[] };
}

export interface EmployeeNoticePeriod {
  request_id:                 string;
  request_ref:                string;
  separation_type:            string;
  notice_status:              NoticeStatus;
  days_remaining:             number;
  confirmed_last_working_day: string;
  approved_at:                string | null;
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
