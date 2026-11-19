// Links into the Approvals page that open it already filtered, e.g. from a dashboard chart:
//   /dashboard/approvals?section=approvals&type=leave&status=rejected&month=2026-11
// Pure, so the building and the reading can be tested without a browser. Anything unknown in the link is ignored, never an error.

import type { ApprovalKind, DisplayStatus } from "@/app/dashboard/approvals/_data";

const KINDS: readonly ApprovalKind[] = ["leave", "wfh", "expense", "attendance_correction", "separation"];
const STATUSES: readonly DisplayStatus[] = ["pending", "approved", "rejected", "cancelled"];
const MONTH = /^(\d{4})-(0[1-9]|1[0-2])$/;

export interface ApprovalLinkFilters {
  type?: ApprovalKind;
  status?: DisplayStatus;
  /** First and last day of the month, as YYYY-MM-DD, for the submitted-date filter. */
  dateFrom?: string;
  dateTo?: string;
}

export interface ApprovalLinkInput {
  type: ApprovalKind;
  status: DisplayStatus;
  /** YYYY-MM; leave out to cover every month. */
  month?: string | null;
}

export function buildApprovalsLink({ type, status, month }: ApprovalLinkInput): string {
  const params = new URLSearchParams({ section: "approvals", type, status });
  if (month && MONTH.test(month)) params.set("month", month);
  return `/dashboard/approvals?${params.toString()}`;
}

function monthRange(month: string): { dateFrom: string; dateTo: string } | null {
  const match = MONTH.exec(month);
  if (!match) return null;
  const year = Number(match[1]);
  const monthNumber = Number(match[2]);
  const lastDay = new Date(year, monthNumber, 0).getDate();
  const mm = match[2];
  return { dateFrom: `${year}-${mm}-01`, dateTo: `${year}-${mm}-${String(lastDay).padStart(2, "0")}` };
}

export function parseApprovalsLink(params: { get(name: string): string | null } | null): ApprovalLinkFilters {
  if (!params) return {};
  const type = params.get("type");
  const status = params.get("status");
  const month = params.get("month");
  const range = month ? monthRange(month) : null;
  return {
    ...(KINDS.includes(type as ApprovalKind) ? { type: type as ApprovalKind } : {}),   // checked against the list on the line above
    ...(STATUSES.includes(status as DisplayStatus) ? { status: status as DisplayStatus } : {}),   // same
    ...(range ?? {}),
  };
}
