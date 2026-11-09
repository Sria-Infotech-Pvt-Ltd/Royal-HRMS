// Pure helpers behind the Manager dashboard (/dashboard/team). Every number is derived here from what the existing
// manager and approval APIs return, so nothing on the screen is typed in. A figure with no data source is null (a dash).
import type { ApprovalItem, ApprovalKind } from "@/app/dashboard/approvals/_data";
import type { KindCount } from "@/lib/approvalOverview";
import type { ManagerTeamAttendanceEntry } from "@/types/managerDashboard";

const PRESENT_STATUSES = new Set(["present", "late", "half_day", "incomplete"]);

export interface TeamBreakdown {
  total: number;
  present: number;
  onLeave: number;
  absent: number;
  /** Work-from-home is not part of the attendance status the API returns, so it has no figure. */
  workFromHome: null;
}

/** Today's team split, from each direct report's attendance status. Weekly offs and holidays count in the total only. */
export function teamBreakdown(entries: ManagerTeamAttendanceEntry[]): TeamBreakdown {
  return {
    total: entries.length,
    present: entries.filter(entry => PRESENT_STATUSES.has(entry.status)).length,
    onLeave: entries.filter(entry => entry.status === "on_leave").length,
    absent: entries.filter(entry => entry.status === "absent").length,
    workFromHome: null,
  };
}

export interface DonutArc {
  key: string;
  label: string;
  value: number | null;
  color: string;
  /** stroke-dasharray / stroke-dashoffset for a circle of the radius given to donutArcs. */
  dash: string;
  offset: number;
}

/** The ring around the team count: one arc per status, sized by its share of the team. A null figure draws no arc. */
export function donutArcs(breakdown: TeamBreakdown, radius: number): DonutArc[] {
  const circumference = 2 * Math.PI * radius;
  const parts = [
    { key: "present", label: "Present", value: breakdown.present, color: "#17905a" },
    { key: "leave", label: "On Leave", value: breakdown.onLeave, color: "#f59e0b" },
    { key: "wfh", label: "WFH", value: breakdown.workFromHome, color: "#a78bfa" },
    { key: "absent", label: "Absent", value: breakdown.absent, color: "#cbd5e1" },
  ];
  let used = 0;
  return parts.map(part => {
    const share = breakdown.total > 0 && part.value ? part.value / breakdown.total : 0;
    const length = share * circumference;
    const arc = { ...part, dash: `${length} ${circumference - length}`, offset: -used };
    used += length;
    return arc;
  });
}

export interface TeamApprovalRow {
  key: ApprovalKind;
  label: string;
  sub: string;
  count: number;
}

const LABELS: Record<ApprovalKind, string> = {
  leave: "Leave Requests", wfh: "Work From Home", expense: "Expense Requests",
  attendance_correction: "Attendance Regularization", separation: "Separation Requests",
};

/** The rows of "Pending Team Approvals": only workflows this manager may approve (absent kinds are never shown as zero). */
export function teamApprovalRows(team: KindCount[]): TeamApprovalRow[] {
  return team.map(count => ({
    key: count.kind, label: LABELS[count.kind],
    sub: `${count.pending} request${count.pending === 1 ? "" : "s"} from your team`, count: count.pending,
  }));
}

export function totalTeamPending(rows: TeamApprovalRow[]): number {
  return rows.reduce((sum, row) => sum + row.count, 0);
}

/** A tile's number for one workflow, or null (a dash) when the manager cannot approve that workflow. */
export function pendingFor(team: KindCount[], kind: ApprovalKind): number | null {
  return team.find(count => count.kind === kind)?.pending ?? null;
}

/**
 * Requests submitted this month that are still waiting on this person, per workflow. The approval lists only hold what
 * is waiting for the viewer, so this is deliberately "waiting", not every request the team made this month.
 */
export function waitingThisMonth(items: ApprovalItem[], now: Date): Record<ApprovalKind, number> {
  const result: Record<ApprovalKind, number> = { leave: 0, wfh: 0, expense: 0, attendance_correction: 0, separation: 0 };
  for (const item of items) {
    const submitted = new Date(item.submittedAt);
    const isThisMonth = submitted.getFullYear() === now.getFullYear() && submitted.getMonth() === now.getMonth();
    if (item.displayStatus === "pending" && isThisMonth) result[item.kind] += 1;
  }
  return result;
}
