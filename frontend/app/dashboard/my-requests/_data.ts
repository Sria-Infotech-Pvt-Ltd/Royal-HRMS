import { LeaveRequest } from "../leave/_data";
import type { Expense } from "../expenses/_components/ExpenseClaims";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import { HR_HELP_DOCUMENT_TOPIC, type HrHelpRequest } from "@/types/hrHelp";
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

export type MyRequestKind = "leave" | "expense" | "attendance_correction" | "wfh" | "hr_help";
// "completed" is distinct from "approved": it only applies to a resolved
// HRHelpRequest whose topic is document_request (e.g. an employment letter
// request) — a deliverable actually handed back, not just an approved
// workflow step. See hrHelpToDisplayStatus below for the real signal used.
export type DisplayStatus = "pending" | "approved" | "rejected" | "cancelled" | "completed";

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
  raw:            LeaveRequest | Expense | MyCorrectionRequest | WorkFromHomeRequest | HrHelpRequest;
}

// ─── Tabs / badges ──────────────────────────────────────────────────────────────

export const REQUEST_TABS: { key: "all" | MyRequestKind; label: string; icon: string }[] = [
  { key: "all",                   label: "All Requests",         icon: "ti-list-details" },
  { key: "leave",                 label: "Leave",                icon: "ti-beach"         },
  { key: "wfh",                   label: "Work From Home",       icon: "ti-home-2"        },
  { key: "expense",               label: "Expense",               icon: "ti-receipt"       },
  { key: "attendance_correction", label: "Attendance Correction", icon: "ti-clock-edit"    },
  { key: "hr_help",               label: "HR Help",              icon: "ti-headset"       },
];

// bg derives from the same token as color via color-mix, rather than a fixed
// rgba tint — two of the previous rgba values didn't even match their own
// color token's hex (leave/expense), and none of them adapted to dark mode.
export const TYPE_META: Record<MyRequestKind, { label: string; icon: string; color: string; bg: string }> = {
  leave:                 { label: "Leave",                 icon: "ti-beach",     color: "var(--success)", bg: "color-mix(in srgb, var(--success) 10%, transparent)"  },
  wfh:                   { label: "Work From Home",        icon: "ti-home-2",    color: "var(--primary)", bg: "color-mix(in srgb, var(--primary) 10%, transparent)"  },
  expense:               { label: "Expense",               icon: "ti-receipt",   color: "var(--warn)",    bg: "color-mix(in srgb, var(--warn) 10%, transparent)"  },
  attendance_correction: { label: "Attendance Correction", icon: "ti-clock-edit", color: "var(--info)",    bg: "color-mix(in srgb, var(--info) 10%, transparent)" },
  hr_help:               { label: "HR Help",               icon: "ti-headset",   color: "var(--on-variant)", bg: "color-mix(in srgb, var(--on-variant) 10%, transparent)" },
};

// "completed" uses badge-info (blue) rather than badge-success (green,
// already "approved") — a genuinely distinct colour for a genuinely
// distinct real state, not a re-skin of approved.
export const STATUS_BADGE_CLASS: Record<DisplayStatus, string> = {
  pending:   "badge badge-warn",
  approved:  "badge badge-success",
  rejected:  "badge badge-error",
  cancelled: "badge badge-neutral",
  completed: "badge badge-info",
};

export const STATUS_LABEL: Record<DisplayStatus, string> = {
  pending:   "Pending",
  approved:  "Approved",
  rejected:  "Rejected",
  cancelled: "Cancelled",
  completed: "Completed",
};

export const STATUS_FILTERS: { key: "all" | DisplayStatus; label: string }[] = [
  { key: "all",       label: "All Statuses" },
  { key: "pending",   label: "Pending"      },
  { key: "approved",  label: "Approved"     },
  { key: "rejected",  label: "Rejected"     },
  { key: "cancelled", label: "Cancelled"    },
  { key: "completed", label: "Completed"    },
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

/** HRHelpRequest has its own status vocabulary (open/in_progress/resolved),
 *  not the pending/approved/rejected/cancelled set the other request kinds
 *  use — so it needs its own mapping rather than reusing toDisplayStatus
 *  (which would otherwise fall through "resolved" into "cancelled").
 *  "resolved" only becomes "completed" for topic === document_request
 *  (e.g. an employment letter) — the real, already-stored distinction that
 *  makes a resolved *document* request different from a resolved query;
 *  everything else resolved is a plain "approved"/closed outcome. */
export function hrHelpToDisplayStatus(status: HrHelpRequest["status"], topic: string): DisplayStatus {
  if (status === "open" || status === "in_progress") return "pending";
  if (topic === HR_HELP_DOCUMENT_TOPIC) return "completed";
  return "approved";
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

// EmployeeRequestModal.tsx has no dedicated "request type" field on the
// backend — it folds the picked type (e.g. "Employment letter") into the
// free-text message as "Request type: <label>. Subject: ...". Recover it
// here purely for display so the row reads "Employment letter" rather than
// the coarser topic_display ("Document request"); when the request came
// from elsewhere (e.g. HrHelpTab.tsx's plain form) the prefix is absent and
// this falls back to topic_display — no data is invented either way.
const REQUEST_TYPE_PREFIX = /^Request type:\s*([^.]+)\./;

function hrHelpTitle(r: HrHelpRequest): string {
  const match = REQUEST_TYPE_PREFIX.exec(r.message);
  return match ? match[1].trim() : r.topic_display;
}

export function hrHelpToMyItem(r: HrHelpRequest): MyRequestItem {
  return {
    key:             `hr_help:${r.id}`,
    kind:            "hr_help",
    id:              r.id,
    requestCode:     r.request_ref,
    title:           hrHelpTitle(r),
    detailSecondary: r.message.length > 80 ? `${r.message.slice(0, 80)}…` : r.message,
    submittedAt:     r.created_at,
    status:          r.status,
    displayStatus:   hrHelpToDisplayStatus(r.status, r.topic),
    approver:        r.assigned_to_name || "—",
    lastUpdated:     r.resolved_at || r.updated_at,
    canCancel:       false,
    raw:             r,
  };
}
