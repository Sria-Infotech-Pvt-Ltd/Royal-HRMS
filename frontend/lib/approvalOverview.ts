// Counts for the My Approvals overview, from the same rows the Team Approvals tab shows. Pure so it can be tested.
//
// Every row here already comes from a workflow API that scopes it to the signed-in user (assigned L1/L2, direct reports,
// branch, or everything for a full-access user), so these counts can never include a request the server would not show.
// "Needs my action" is the server's own per-row answer (ApprovalItem.canAction): it is not recomputed in the browser.
import type { ApprovalItem, ApprovalKind } from "@/app/dashboard/approvals/_data";

export interface KindCount {
  kind: ApprovalKind;
  pending: number;
  needsMyAction: number;
}

export const KIND_LABELS: Record<ApprovalKind, string> = {
  leave: "Leave",
  wfh: "Work from home",
  expense: "Expenses",
  attendance_correction: "Attendance regularization",
  separation: "Separation",
};

// How each workflow decides who sees a request — they are deliberately not identical, so the screen says so.
export const KIND_SCOPE_NOTES: Record<ApprovalKind, string> = {
  leave: "Assigned approvers: L1 (manager) first, then L2 (HR). A full-access user sees all.",
  wfh: "Assigned approvers: L1 (manager) first, then L2 (HR). A full-access user sees all.",
  expense: "Managers see their direct reports; HR sees the employees assigned to them, else their branch.",
  attendance_correction: "Reporting managers and HR. Decided on the request.",
  separation: "Managers see direct reports; HR sees their branch. Each stage is decided on its own page.",
};

const ORDER: ApprovalKind[] = ["leave", "wfh", "expense", "attendance_correction", "separation"];

/** Counts for the workflows in `kinds` only (default: all). A workflow the person cannot approve is simply left out. */
export function summariseTeamApprovals(items: ApprovalItem[], kinds: readonly ApprovalKind[] = ORDER): KindCount[] {
  return ORDER.filter(kind => kinds.includes(kind)).map(kind => {
    const pending = items.filter(item => item.kind === kind && item.displayStatus === "pending");
    return { kind, pending: pending.length, needsMyAction: pending.filter(item => item.canAction).length };
  });
}
