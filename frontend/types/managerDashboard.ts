export interface ManagerKPIs {
  team_size:         number;
  pending_approvals: number;
  on_leave_today:    number;
  attendance_rate:   number;
}

export interface PendingApprovalItem {
  type:          "leave" | "expense";
  id:            string;
  employee_name: string;
  created_at:    string;
  details:       Record<string, unknown>;
}

export interface PendingApprovalsResponse {
  total_pending: number;
  items:         PendingApprovalItem[];
}

export interface TeamAttendanceRow {
  employee_id:    string;
  employee_name:  string;
  status:         string;
  status_display: string;
  first_punch_in: string | null;
}

export interface TeamAttendanceResponse {
  team_size:     number;
  present_count: number;
  rows:          TeamAttendanceRow[];
}

export interface UpcomingLeaveItem {
  id:            string;
  employee_name: string;
  leave_type:    string;
  start_date:    string;
  end_date:      string;
  total_days:    number;
}

export interface UpcomingLeaveResponse {
  items: UpcomingLeaveItem[];
}

export interface RecentActivityItem {
  type:          "clock_in" | "leave_applied";
  employee_name: string;
  created_at:    string;
  details?:      Record<string, unknown>;
}

export interface RecentActivityResponse {
  items: RecentActivityItem[];
}
