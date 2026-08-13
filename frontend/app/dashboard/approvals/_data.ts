import { LeaveRequest, fmtDate as fmtDateOnly } from "../leave/_data";
import type { SeparationRequest } from "@/types/separation";

// ─── Kind-specific request shapes (as returned by their own list endpoints) ───

export interface ExpenseReceipt {
  id:  string;
  url: string | null;
}

export interface ExpenseRequest {
  expense_number: string | number;
  expense_ref?:   string;
  title:          string;
  category:       string;
  amount:         string | number;
  expense_date:   string;
  description:    string;
  status:         "pending" | "approved" | "rejected";
  employee_name:  string;
  employee_email?: string;
  branch_name:    string;
  receipts:       ExpenseReceipt[];
  created_at:     string;
  remarks?:       string;
}

export interface CorrectionRequest {
  id:               string;
  employee_id:      string; // holds the employee CODE, not a numeric pk
  name:             string;
  department:       string;
  branch:           string;
  date:             string; // date the correction applies to (YYYY-MM-DD)
  punch_type:       "IN" | "OUT" | "BOTH";
  original_in:      string | null; // "HH:MM"
  original_out:     string | null;
  requested_in:     string | null;
  requested_out:    string | null;
  reason:           string;
  notes?:           string;
  status:           "pending" | "l2_pending" | "approved" | "rejected";
  l1_approver_name: string | null;
  l1_status:        "approved" | "rejected" | null;
  l1_remarks:       string;
  l2_approver_name: string | null;
  l2_status:        "approved" | "rejected" | null;
  l2_remarks:       string;
  can_action:       boolean;
  reviewed_by:      string | null;
  reviewed_at:      string | null;
  created_at:       string;
}

export interface PaginatedResponse<T> {
  results:     T[];
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
}

export type LeaveListResponse      = PaginatedResponse<LeaveRequest>;
export type ExpenseListResponse    = PaginatedResponse<ExpenseRequest>;
export type CorrectionListResponse = PaginatedResponse<CorrectionRequest>;
export type SeparationListResponse = PaginatedResponse<SeparationRequest>;

// ─── Unified shape the table / drawer / toolbar actually work with ────────────

export type ApprovalKind = "leave" | "expense" | "attendance_correction" | "separation";
export type DisplayStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface ApprovalItem {
  key:            string; // unique across all kinds — `${kind}:${id}`
  kind:           ApprovalKind;
  id:             string; // raw id used for API calls
  employeeName:   string;
  employeeCode:   string; // "—" when the source has no employee identifier (expense)
  department?:    string;
  branch?:        string;
  status:         string; // raw backend status (pending / l2_pending / approved / rejected / cancelled)
  displayStatus:  DisplayStatus;
  submittedAt:    string; // raw created_at, kind-specific format — use fmtSubmitted() to render
  detailPrimary:  string;
  detailSecondary: string;
  detailTertiary?: string;
  canAction:      boolean;
  raw:            LeaveRequest | ExpenseRequest | CorrectionRequest | SeparationRequest;
}

// ─── Tabs / badges / chips config ──────────────────────────────────────────────

export const TYPE_TABS: { key: "all" | ApprovalKind; label: string; icon: string }[] = [
  { key: "all",                    label: "All Requests",          icon: "ti-list-details"    },
  { key: "leave",                  label: "Leave",                 icon: "ti-beach"            },
  { key: "expense",                label: "Expense",                icon: "ti-receipt"          },
  { key: "attendance_correction",  label: "Attendance Correction",  icon: "ti-calendar-time"    },
  { key: "separation",             label: "Separation",             icon: "ti-logout"           },
];

export const TYPE_BADGE: Record<ApprovalKind, { label: string; cls: string }> = {
  leave:                  { label: "Leave",                 cls: "ta-type-leave"                 },
  expense:                { label: "Expense",               cls: "ta-type-expense"               },
  attendance_correction:  { label: "Attendance Correction", cls: "ta-type-attendance_correction"  },
  separation:             { label: "Separation",            cls: "ta-type-separation"            },
};

export const STATUS_CHIP: Record<DisplayStatus, { label: string; cls: string }> = {
  pending:   { label: "Pending",   cls: "ta-status-pending"   },
  approved:  { label: "Approved",  cls: "ta-status-approved"  },
  rejected:  { label: "Rejected",  cls: "ta-status-rejected"  },
  cancelled: { label: "Cancelled", cls: "ta-status-cancelled" },
};

export const STATUS_FILTERS: { key: "all" | DisplayStatus; label: string }[] = [
  { key: "all",      label: "All Statuses" },
  { key: "pending",  label: "Pending"      },
  { key: "approved", label: "Approved"     },
  { key: "rejected", label: "Rejected"     },
];

const PUNCH_LABEL: Record<CorrectionRequest["punch_type"], string> = {
  IN:   "Check-in Correction",
  OUT:  "Check-out Correction",
  BOTH: "Check-in & Check-out Correction",
};

// ─── Formatting helpers ────────────────────────────────────────────────────────

/** Leave/expense created_at is full ISO; correction's is "YYYY-MM-DD HH:MM" —
 *  normalise both to something `new Date()` can parse before formatting. */
export function fmtSubmitted(raw: string): string {
  if (!raw) return "—";
  const iso = raw.includes("T") ? raw : raw.replace(" ", "T");
  const d = new Date(iso);
  if (isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function toSortableTime(raw: string): number {
  if (!raw) return 0;
  const iso = raw.includes("T") ? raw : raw.replace(" ", "T");
  const d = new Date(iso);
  return isNaN(d.getTime()) ? 0 : d.getTime();
}

function fmtTime12h(hhmm: string | null): string {
  if (!hhmm) return "—";
  const [hStr, mStr] = hhmm.split(":");
  const h = parseInt(hStr, 10);
  if (isNaN(h)) return hhmm;
  const period = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${String(h12).padStart(2, "0")}:${mStr ?? "00"} ${period}`;
}

export function toDisplayStatus(status: string): DisplayStatus {
  if (status === "pending" || status === "l2_pending" || status === "stage2_pending") return "pending";
  if (status === "approved") return "approved";
  if (status === "rejected") return "rejected";
  return "cancelled";
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function fmtAmount(amount: string | number): string {
  const n = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(n)) return "₹0";
  return `₹${n.toLocaleString("en-IN")}`;
}

// ─── Normalisation: kind-specific record → unified ApprovalItem ───────────────

export function leaveToItem(r: LeaveRequest): ApprovalItem {
  return {
    key:            `leave:${r.id}`,
    kind:           "leave",
    id:             r.id,
    employeeName:   r.employee_name,
    employeeCode:   r.employee_code || "—",
    department:     r.employee_dept,
    branch:         r.employee_branch,
    status:         r.status,
    displayStatus:  toDisplayStatus(r.status),
    submittedAt:    r.created_at,
    detailPrimary:  r.leave_type_display,
    detailSecondary: `${fmtDateOnly(r.start_date)} - ${fmtDateOnly(r.end_date)}`,
    detailTertiary: `${r.total_days} Day${r.total_days === 1 ? "" : "s"}`,
    canAction:      r.can_approve ?? (r.status === "pending" || r.status === "l2_pending"),
    raw:            r,
  };
}

export function expenseToItem(r: ExpenseRequest): ApprovalItem {
  return {
    key:            `expense:${r.expense_number}`,
    kind:           "expense",
    id:             String(r.expense_number),
    employeeName:   r.employee_name,
    employeeCode:   "—",
    branch:         r.branch_name,
    status:         r.status,
    displayStatus:  toDisplayStatus(r.status),
    submittedAt:    r.created_at,
    detailPrimary:  r.title || "Expense",
    detailSecondary: fmtAmount(r.amount),
    canAction:      r.status === "pending",
    raw:            r,
  };
}

export function correctionToItem(r: CorrectionRequest): ApprovalItem {
  const showIn  = r.punch_type !== "OUT";
  const showOut = r.punch_type !== "IN";
  const arrows  = [
    showIn  ? `${fmtTime12h(r.original_in)} → ${fmtTime12h(r.requested_in)}`   : null,
    showOut ? `${fmtTime12h(r.original_out)} → ${fmtTime12h(r.requested_out)}` : null,
  ].filter(Boolean);

  return {
    key:            `attendance_correction:${r.id}`,
    kind:           "attendance_correction",
    id:             r.id,
    employeeName:   r.name,
    employeeCode:   r.employee_id || "—",
    department:     r.department,
    branch:         r.branch,
    status:         r.status,
    displayStatus:  toDisplayStatus(r.status),
    submittedAt:    r.created_at,
    detailPrimary:  PUNCH_LABEL[r.punch_type] ?? "Attendance Correction",
    detailSecondary: arrows.join("  ·  "),
    detailTertiary: fmtDateOnly(r.date),
    canAction:      r.can_action,
    raw:            r,
  };
}

export function separationToItem(r: SeparationRequest): ApprovalItem {
  return {
    key:            `separation:${r.id}`,
    kind:           "separation",
    id:             r.id,
    employeeName:   r.employee_name,
    employeeCode:   r.employee_code || "—",
    department:     r.employee_department,
    status:         r.status,
    displayStatus:  toDisplayStatus(r.status),
    submittedAt:    r.created_at,
    detailPrimary:  r.separation_type_display,
    detailSecondary: `Last day: ${fmtDateOnly(r.proposed_last_working_day)}`,
    detailTertiary: r.reason_display,
    canAction:      r.can_approve,
    raw:            r,
  };
}

// ─── Approve/reject helpers reused by the ApprovalModal (leave/expense email flow) ──

export function leaveAutoVars(req: LeaveRequest): Record<string, string> {
  return {
    LEAVE_TYPE:    req.leave_type_display ?? req.leave_type ?? "",
    START_DATE:    fmtDateOnly(req.start_date),
    END_DATE:      fmtDateOnly(req.end_date),
    TOTAL_DAYS:    String(req.total_days ?? ""),
    REASON:        req.reason ?? "",
    EMPLOYEE_CODE: req.employee_code ?? "",
    EMPLOYEE_ID:   req.employee_code ?? "",
  };
}
