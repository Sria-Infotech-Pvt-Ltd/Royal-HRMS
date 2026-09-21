import { LeaveRequest } from "../leave/_data";
import type { Expense } from "../expenses/_components/ExpenseClaims";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import { formatDate } from "@/lib/formatDate";

// ─── Correction request shape (own corrections, /attendance/corrections/my/) ──
// The single source of truth for "my attendance correction" rows — used by
// both the My Attendance → Attendance Corrections tab and the My Requests →
// Attendance Correction tab, so there is exactly one shape/one fetch to keep
// in sync instead of duplicating an inline interface in every screen.

export interface MyCorrectionRequest {
  id:               string;
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

// ─── Unified "my request" shape ───────────────────────────────────────────────

export type MyRequestKind = "leave" | "expense" | "attendance_correction" | "wfh";
export type DisplayStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface MyRequestItem {
  key:            string; // unique across kinds — `${kind}:${id}`
  kind:           MyRequestKind;
  id:             string; // raw id, used to open the right detail view / API calls
  requestCode:    string; // short display reference, e.g. "EXP002" / "LR-3F9A21"
  title:          string;
  detailSecondary: string; // date range / amount / time-change, shown under the title
  submittedAt:    string;
  status:         string;
  displayStatus:  DisplayStatus;
  approver:       string;
  lastUpdated:    string;
  canCancel:      boolean;
  raw:            LeaveRequest | Expense | MyCorrectionRequest | WorkFromHomeRequest;
}

// ─── Tabs / badges ──────────────────────────────────────────────────────────────

export const REQUEST_TABS: { key: "all" | MyRequestKind; label: string; icon: string }[] = [
  { key: "all",                   label: "All Requests",         icon: "ti-list-details" },
  { key: "leave",                 label: "Leave",                icon: "ti-beach"         },
  { key: "wfh",                   label: "Work From Home",       icon: "ti-home-2"        },
  { key: "expense",               label: "Expense",               icon: "ti-receipt"       },
  { key: "attendance_correction", label: "Attendance Correction", icon: "ti-clock-edit"    },
];

export const TYPE_META: Record<MyRequestKind, { label: string; icon: string; color: string; bg: string }> = {
  leave:                 { label: "Leave",                 icon: "ti-beach",     color: "var(--success)", bg: "rgba(22,163,74,0.10)"  },
  wfh:                   { label: "Work From Home",        icon: "ti-home-2",    color: "var(--primary)", bg: "rgba(124,58,237,0.10)"  },
  expense:               { label: "Expense",               icon: "ti-receipt",   color: "var(--warn)",    bg: "rgba(217,119,6,0.10)"  },
  attendance_correction: { label: "Attendance Correction", icon: "ti-clock-edit", color: "var(--info)",    bg: "rgba(37,99,235,0.10)" },
};

export const STATUS_BADGE_CLASS: Record<DisplayStatus, string> = {
  pending:   "badge badge-warn",
  approved:  "badge badge-success",
  rejected:  "badge badge-error",
  cancelled: "badge badge-neutral",
};

export const STATUS_LABEL: Record<DisplayStatus, string> = {
  pending:   "Pending",
  approved:  "Approved",
  rejected:  "Rejected",
  cancelled: "Cancelled",
};

export const STATUS_FILTERS: { key: "all" | DisplayStatus; label: string }[] = [
  { key: "all",       label: "All Statuses" },
  { key: "pending",   label: "Pending"      },
  { key: "approved",  label: "Approved"     },
  { key: "rejected",  label: "Rejected"     },
  { key: "cancelled", label: "Cancelled"    },
];

const PUNCH_LABEL: Record<MyCorrectionRequest["punch_type"], string> = {
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
  return formatDate(d);
}

export function toSortableTime(raw: string): number {
  if (!raw) return 0;
  const iso = raw.includes("T") ? raw : raw.replace(" ", "T");
  const d = new Date(iso);
  return isNaN(d.getTime()) ? 0 : d.getTime();
}

export function fmtTime12h(hhmm: string | null): string {
  if (!hhmm) return "—";
  const [hStr, mStr] = hhmm.split(":");
  const h = parseInt(hStr, 10);
  if (isNaN(h)) return hhmm;
  const period = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${String(h12).padStart(2, "0")}:${mStr ?? "00"} ${period}`;
}

export function toDisplayStatus(status: string): DisplayStatus {
  if (status === "pending" || status === "l2_pending") return "pending";
  if (status === "approved") return "approved";
  if (status === "rejected") return "rejected";
  return "cancelled";
}

function fmtDateOnly(iso: string): string {
  if (!iso) return "—";
  return formatDate(iso);
}

function fmtShort(iso: string): string {
  if (!iso) return "—";
  return new Date(iso + "T12:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

// ─── Normalisation: kind-specific record → unified MyRequestItem ──────────────

export function leaveToMyItem(r: LeaveRequest): MyRequestItem {
  return {
    key:             `leave:${r.id}`,
    kind:            "leave",
    id:              r.id,
    requestCode:     `LR-${r.id.slice(0, 6).toUpperCase()}`,
    title:           r.leave_type_display,
    detailSecondary: `${fmtShort(r.start_date)} - ${fmtShort(r.end_date)} · ${r.total_days} day${r.total_days === 1 ? "" : "s"}`,
    submittedAt:     r.created_at,
    status:          r.status,
    displayStatus:   toDisplayStatus(r.status),
    approver:        r.approved_by || r.l1_approver_name || "—",
    lastUpdated:     r.approved_at || r.l1_actioned_at || r.created_at,
    canCancel:       r.can_cancel ?? (r.status === "pending" || r.status === "l2_pending"),
    raw:             r,
  };
}

export function expenseToMyItem(r: Expense): MyRequestItem {
  return {
    key:             `expense:${r.expense_number}`,
    kind:            "expense",
    id:              String(r.expense_number),
    requestCode:     r.expense_ref,
    title:           r.title || "Expense",
    detailSecondary: `₹${parseFloat(String(r.amount)).toLocaleString("en-IN")}`,
    submittedAt:     r.created_at,
    status:          r.status,
    displayStatus:   toDisplayStatus(r.status),
    approver:        "—",
    lastUpdated:     r.created_at,
    canCancel:       false,
    raw:             r,
  };
}

export function wfhToMyItem(r: WorkFromHomeRequest): MyRequestItem {
  const days = Math.round((new Date(r.end_date).getTime() - new Date(r.start_date).getTime()) / 86_400_000) + 1;
  return {
    key:             `wfh:${r.id}`,
    kind:            "wfh",
    id:              r.id,
    requestCode:     `WFH-${r.id.slice(0, 6).toUpperCase()}`,
    title:           r.location_label || "Work From Home",
    detailSecondary: `${fmtShort(r.start_date)} - ${fmtShort(r.end_date)} · ${days} day${days === 1 ? "" : "s"}`,
    submittedAt:     r.created_at,
    status:          r.status,
    displayStatus:   toDisplayStatus(r.status),
    approver:        r.l2_approver_name || r.l1_approver_name || "—",
    lastUpdated:     r.l2_actioned_at || r.l1_actioned_at || r.created_at,
    canCancel:       r.can_cancel ?? (r.status === "pending" || r.status === "l2_pending"),
    raw:             r,
  };
}

export function correctionToMyItem(r: MyCorrectionRequest): MyRequestItem {
  const showIn  = r.punch_type !== "OUT";
  const showOut = r.punch_type !== "IN";
  const arrows  = [
    showIn  ? `${fmtTime12h(r.original_in)} → ${fmtTime12h(r.requested_in)}`   : null,
    showOut ? `${fmtTime12h(r.original_out)} → ${fmtTime12h(r.requested_out)}` : null,
  ].filter(Boolean);

  return {
    key:             `attendance_correction:${r.id}`,
    kind:            "attendance_correction",
    id:              r.id,
    requestCode:     `AC-${r.id.slice(0, 6).toUpperCase()}`,
    title:           PUNCH_LABEL[r.punch_type] ?? "Attendance Correction",
    detailSecondary: `${fmtDateOnly(r.date)} · ${arrows.join(", ")}`,
    submittedAt:     r.created_at,
    status:          r.status,
    displayStatus:   toDisplayStatus(r.status),
    approver:        r.l2_approver_name || r.l1_approver_name || "—",
    lastUpdated:     r.reviewed_at || r.created_at,
    canCancel:       false,
    raw:             r,
  };
}
