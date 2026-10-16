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

/** One month's recorded movements — not a month-end balance. */
export interface LeaveMonthRow {
  month:             number;
  label:             string;
  monthly_credit:    number;
  other_adjustments: number;
  used:              number;
}

export interface LeaveBalance {
  leave_type:      string;
  total_days:      number;
  used_days:       number;
  remaining:       number;
  carried_forward: number;
  // Optional: responses cached before these fields existed won't have them.
  leave_type_label?:      string;
  credit_schedule?:       "annual" | "monthly";
  monthly_carry_forward?: boolean;
  monthly?: { months: LeaveMonthRow[]; used_not_itemised: number };
  /** Monthly-schedule leave types only (null otherwise): the full month-by-month statement. */
  statement?: LeaveStatement | null;
}

export interface LeaveStatementMonth {
  month:       number;
  label:       string;
  carry_off:   boolean;   // this month's credit expires if unused
  closed:      boolean;
  carried_in:  number;
  credit:      number;
  used:        number;
  pending:     number;
  expired:     number;
  credit_left: number;    // this month's credit still usable (open no-carry months)
  closing:     number;
}

export interface LeaveStatement {
  opening:           number;   // opening / carried-in / lump / adjustments — never expire
  adjustments:       number;
  used_not_itemised: number;
  months:            LeaveStatementMonth[];
  total_pending:     number;
  reconciled:        boolean;
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
