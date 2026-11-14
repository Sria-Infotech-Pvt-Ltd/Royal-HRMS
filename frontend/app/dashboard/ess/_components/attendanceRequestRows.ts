// Rows for the Attendance tab's "Attendance requests" card: attendance corrections and work-from-home requests, newest
// first. Both change how an employee's days are counted, so both belong here; HR help tickets, leave and expenses do not
// and are never passed in. Pure, so it can be tested without rendering the tab.

import type { WorkFromHomeRequest } from "@/types/workFromHome";
import { STATUS_LABEL, toDisplayStatus, wfhToMyItem, type MyCorrectionRequest } from "../../my-requests/_data";

export const MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export interface AttendanceRequestRow {
  key: string;
  title: string;
  detail: string;
  statusLabel: string;
  isApproved: boolean;
  /** ISO timestamp the request was created; rows are sorted on it, newest first. */
  createdAt: string;
  /** Exactly one of these is set: the request behind the row, which opens its own detail dialog. */
  correction?: MyCorrectionRequest;
  wfh?: WorkFromHomeRequest;
}

export function correctionTitle(dateIso: string): string {
  const date = new Date(`${dateIso}T12:00:00`);
  return Number.isNaN(date.getTime()) ? "Correction" : `${date.getDate()} ${MONTH_LONG[date.getMonth()]} correction`;
}

function correctionRow(request: MyCorrectionRequest): AttendanceRequestRow {
  const status = toDisplayStatus(request.status);
  const approver = request.l2_approver_name || request.l1_approver_name;
  return {
    key: `correction:${request.id}`,
    title: correctionTitle(request.date),
    detail: `${status === "approved" && approver ? `Approved by ${approver}` : STATUS_LABEL[status]} · View details`,
    statusLabel: STATUS_LABEL[status].toUpperCase(),
    isApproved: status === "approved",
    createdAt: request.created_at,
    correction: request,
  };
}

function wfhRow(request: WorkFromHomeRequest): AttendanceRequestRow {
  const item = wfhToMyItem(request);
  const approvedBy = item.displayStatus === "approved" && item.approver !== "—" ? `Approved by ${item.approver}` : STATUS_LABEL[item.displayStatus];
  return {
    key: item.key,
    title: item.title === "Work From Home" ? "Work from home" : `Work from home · ${item.title}`,
    detail: `${item.detailSecondary} · ${approvedBy} · View details`,
    statusLabel: STATUS_LABEL[item.displayStatus].toUpperCase(),
    isApproved: item.displayStatus === "approved",
    createdAt: request.created_at,
    wfh: request,
  };
}

export function buildAttendanceRequestRows(
  corrections: MyCorrectionRequest[], wfhRequests: WorkFromHomeRequest[], limit: number,
): AttendanceRequestRow[] {
  return [...corrections.map(correctionRow), ...wfhRequests.map(wfhRow)]
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .slice(0, limit);
}
