export interface TodayAttendance {
  status:                string;
  first_punch_in:        string | null;
  last_punch_out:        string | null;
  total_working_minutes: number;
}

export interface EmployeeKPIs {
  days_present:           number;
  working_days:           number;
  absent_days:            number;
  pending_action_items:   number;
  pending_expense_claims: number;
  pending_documents:      number;
  clocked_in:             boolean;
  today_attendance:       TodayAttendance | null;
}

export interface LeaveBalance {
  leave_type:      string;
  total_days:      number;
  used_days:       number;
  remaining:       number;
  carried_forward: number;
}

export interface LeaveBalanceSummary {
  year:     number;
  lop_days: number;
  balances: LeaveBalance[];
}

export interface ActionItem {
  action_type:    string;
  title:          string;
  description:    string;
  status:         string;
  navigation_url: string;
}

export interface ActionItemsResponse {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     ActionItem[];
}

export interface RecentRequest {
  request_type: "leave" | "expense" | "attendance_correction";
  title:        string;
  applied_date: string;
  status:       string;
  remarks:      string;
  details:      Record<string, unknown>;
}

export interface RecentRequestsResponse {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     RecentRequest[];
}

export interface AttendanceSummary {
  year:                  number;
  month:                 number;
  present_days:          number;
  absent_days:           number;
  late_marks:            number;
  lop_pending:           number;
  half_days:             number;
  leave_days:            number;
  working_days:          number;
  avg_hours_per_day:     number;
  attendance_percentage: number;
  ot_hours:              string;
}

export interface AttendanceStatus {
  clocked_in:     boolean;
  clock_in_time:  string | null;
  clock_out_time: string | null;
  working_hours:  string;
  can_clock_in:   boolean;
  can_clock_out:  boolean;
}

export interface Announcement {
  id:         number;
  title:      string;
  body:       string;
  category:   string;
  visibility: string;
  is_pinned:  boolean;
  posted_by:  string | null;
  created_at: string;
}

export interface BirthdayEmployee {
  employee_id:   string;
  full_name:     string;
  email:         string;
  department:    string;
  designation:   string;
  branch:        string;
  date_of_birth: string;
  days_until:    number;
  message:       string;
}

export interface BirthdaysTodayResponse {
  count:     number;
  birthdays: BirthdayEmployee[];
}

export interface MyBirthdayPerson {
  employee_id:   string;
  full_name:     string;
  email:         string;
  department:    string;
  designation:   string;
  date_of_birth: string | null;
  message:       string;
}

export interface MyBirthdayWidgets {
  team:    MyBirthdayPerson[];
  manager: MyBirthdayPerson | null;
}
