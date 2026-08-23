// ─── Leave type UI metadata ───────────────────────────────────────────────────

export type LeaveTypeKey = "casual" | "earned" | "sick" | "lwp" | "maternity" | "paternity";
export type DurationKey  = "full_day" | "half_morning" | "half_afternoon";
export type ReqStatus    = "pending" | "l2_pending" | "approved" | "rejected" | "cancelled";

export interface LeaveTypeConfig {
  key:         LeaveTypeKey;
  label:       string;
  shortLabel:  string;
  icon:        string;
  color:       string;
  bg:          string;
  isLwp:       boolean;
  requiresDoc: boolean;
}

export const LEAVE_TYPE_CONFIG: Record<LeaveTypeKey, LeaveTypeConfig> = {
  casual:    { key: "casual",    label: "Casual Leave",      shortLabel: "CL",  icon: "ti-beach",          color: "#1e4e8c", bg: "rgba(30,78,140,0.1)",    isLwp: false, requiresDoc: false },
  earned:    { key: "earned",    label: "Earned Leave",      shortLabel: "EL",  icon: "ti-calendar-check", color: "#1b8a6b", bg: "rgba(27,138,107,0.1)",   isLwp: false, requiresDoc: false },
  sick:      { key: "sick",      label: "Sick Leave",        shortLabel: "SL",  icon: "ti-stethoscope",    color: "#0e7c86", bg: "rgba(14,124,134,0.1)",   isLwp: false, requiresDoc: true  },
  lwp:       { key: "lwp",       label: "Leave Without Pay", shortLabel: "LWP", icon: "ti-coin-off",       color: "#b5651d", bg: "rgba(181,101,29,0.1)",   isLwp: true,  requiresDoc: false },
  maternity: { key: "maternity", label: "Maternity Leave",   shortLabel: "ML",  icon: "ti-heart",          color: "#ad95cf", bg: "rgba(173,149,207,0.12)", isLwp: false, requiresDoc: true  },
  paternity: { key: "paternity", label: "Paternity Leave",   shortLabel: "PL",  icon: "ti-baby-carriage",  color: "#5b86c9", bg: "rgba(91,134,201,0.1)",  isLwp: false, requiresDoc: true  },
};

export const LEAVE_TYPES_LIST = Object.values(LEAVE_TYPE_CONFIG);

// ─── API response types ───────────────────────────────────────────────────────

export interface LeavePolicy {
  id:                    number;
  leave_type:            LeaveTypeKey;
  leave_type_display:    string;
  annual_days:           number;
  can_carry_forward:     boolean;
  max_carry_forward_days: number;
  policy_note:           string;
  is_active:             boolean;
  sandwich_leave_enabled: boolean;
  convert_to_lop:        boolean;
  updated_at:            string;
}

export interface LeaveBalance {
  id:                        string;
  leave_type:                LeaveTypeKey;
  leave_type_display:        string;
  year:                      number;
  total_days:                number;
  used_days:                 number;
  carried_forward:           number;
  available_days:            number;
  employee_name:             string;
  carry_forward_expiry_date: string | null; // ISO date, or null when it never expires
}

export interface LeaveRequest {
  id:                 string;
  leave_type:         LeaveTypeKey;
  leave_type_display: string;
  duration:           DurationKey;
  duration_display:   string;
  start_date:         string;
  end_date:           string;
  total_days:         number;
  lop_days:           number;
  reason:             string;
  status:             ReqStatus;
  is_lwp:             boolean;
  employee_name:      string;
  employee_code:      string;
  employee_dept:      string;
  employee_branch:    string;
  l1_approver_name:   string;
  l1_status:          string | null;
  l1_remarks:         string;
  l1_actioned_at:     string | null;
  l2_approver_name:   string;
  l2_status:          string | null;
  l2_remarks:         string;
  l2_actioned_at:     string | null;
  contact_during_leave: string;
  handover_to:        string;
  handover_notes:     string;
  document_url:       string | null;
  created_at:         string;
  can_approve?:       boolean;
  can_cancel?:        boolean;
  approved_by:        string | null;
  approved_at:        string | null;
}

export interface PaginatedResponse<T> {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     T[];
}

export interface LeaveStats {
  total:        number;
  pending:      number;
  approved:     number;
  rejected:     number;
  cancelled:    number;
  lop_days:     number;
  lop_requests: number;
  year:         number;
  balances:     BalanceSummary[];
}

export interface BalanceSummary {
  leave_type:         LeaveTypeKey;
  leave_type_display: string;
  total_days:         number;
  used_days:          number;
  available:          number;
}

export interface LeavePreviewHoliday {
  // Pre-formatted by the backend (e.g. "15 Aug") — display as-is, do not
  // pass through fmtDate (it expects an ISO date and would render "Invalid Date").
  date: string;
  name: string;
}

export interface LeavePreviewWeekOff {
  date: string;  // ISO — safe to pass through fmtDate
  day:  string;  // e.g. "Sunday" — backend-supplied, no need to recompute
}

// Confirmed shape of GET /leave/requests/?action=preview&... — see
// LeavePreview usage in ApplyLeaveForm.tsx for the full field list.
export interface LeavePreview {
  leave_type:             LeaveTypeKey;
  start_date:             string;
  end_date:               string;
  duration:               DurationKey;
  calendar_days:          number;
  company_holidays:       LeavePreviewHoliday[];
  company_holiday_count:  number;
  week_offs:              LeavePreviewWeekOff[];
  week_off_count:         number;
  sandwich_leave_enabled: boolean;
  actual_leave_days:      number;
  available_balance:      number;
  leave_days_used:        number;
  lop_days:               number;
  lop_enabled:            boolean;
  sufficient_balance:     boolean;
  warning:                string | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

export const STATUS_BADGE: Record<ReqStatus, string> = {
  pending:    "badge badge-warn",
  l2_pending: "badge badge-warn",
  approved:   "badge badge-success",
  rejected:   "badge badge-error",
  cancelled:  "badge badge-neutral",
};

export const STATUS_LABEL: Record<ReqStatus, string> = {
  pending:    "Pending Manager Approval",
  l2_pending: "Pending HR Approval",
  approved:   "Approved",
  rejected:   "Rejected",
  cancelled:  "Cancelled",
};

export function fmtDate(iso: string): string {
  if (!iso) return "—";
  return new Date(iso + "T12:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtShortDate(iso: string): string {
  if (!iso) return "—";
  return new Date(iso + "T12:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function calcWorkingDays(from: string, to: string, dur: DurationKey, sandwichEnabled = false): number {
  if (!from) return 0;
  if (dur !== "full_day") return 0.5;
  const a = new Date(from + "T12:00:00");
  const b = to ? new Date(to + "T12:00:00") : a;
  if (b < a) return 0;
  let count = 0;
  const cur = new Date(a);
  while (cur <= b) {
    // Sandwich leave counts every calendar day in the range (weekends and
    // holidays included) — matches the backend's own sandwich-leave day
    // count, regardless of which days are configured as week-offs.
    if (sandwichEnabled || (cur.getDay() !== 0 && cur.getDay() !== 6)) count++;
    cur.setDate(cur.getDate() + 1);
  }
  return count;
}
