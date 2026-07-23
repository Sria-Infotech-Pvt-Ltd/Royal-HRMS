export interface ManagerTeamOverview {
  greeting:                    string;
  manager_name:                string;
  current_date:                string;
  team_size:                   number;
  pending_approvals:           number;
  employees_on_leave_today:    number;
  team_attendance_percentage:  number;
}

export interface ManagerQuickAction {
  id:    string;
  label: string;
  url:   string;
  count: number | null;
}

export type ApprovalType = "leave" | "expense" | "attendance_correction";

export interface ManagerPendingApproval {
  id:            string;
  approval_type: ApprovalType;
  employee_name: string;
  employee_id:   string;
  summary:       string;
  date_from:     string;
  date_to:       string;
  applied_on:    string;
  status:        "pending" | "l2_pending";
}

export interface ManagerBirthdayEntry {
  employee_id:   string;
  full_name:     string;
  email:         string;
  department:    string;
  branch:        string;
  date_of_birth: string;
  days_until:    number;
}

export interface ManagerActivityEntry {
  employee_name: string;
  employee_id:   string;
  action:        string;
  module:        string;
  description:   string;
  created_at:    string;
}

export type AttendanceStatus =
  | "present" | "late" | "half_day" | "incomplete"
  | "on_leave" | "weekly_off" | "holiday" | "absent";

export interface ManagerTeamAttendanceEntry {
  employee_id:   string;
  employee_name: string;
  designation:   string;
  clock_in:      string | null;
  clock_out:     string | null;
  status:        AttendanceStatus;
}

export interface ManagerUpcomingLeave {
  id:            string;
  employee_id:   string;
  employee_name: string;
  leave_type:    string;
  date_from:     string;
  date_to:       string;
  total_days:    number;
  status:        "approved" | "pending" | "l2_pending";
}

export interface ManagerDashboardData {
  team_overview:        ManagerTeamOverview;
  quick_actions:        ManagerQuickAction[];
  pending_approvals:    ManagerPendingApproval[];
  todays_birthdays:     ManagerBirthdayEntry[];
  upcoming_birthdays:   ManagerBirthdayEntry[];
  recent_team_activity: ManagerActivityEntry[];
  team_attendance:      ManagerTeamAttendanceEntry[];
  upcoming_leaves:      ManagerUpcomingLeave[];
}
