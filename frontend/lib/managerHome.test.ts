import { describe, expect, it } from "vitest";
import type { ApprovalItem, ApprovalKind, DisplayStatus } from "@/app/dashboard/approvals/_data";
import type { KindCount } from "@/lib/approvalOverview";
import type { ManagerTeamAttendanceEntry } from "@/types/managerDashboard";
import { donutArcs, pendingFor, teamApprovalRows, teamBreakdown, totalTeamPending, waitingThisMonth } from "./managerHome";

const entry = (status: ManagerTeamAttendanceEntry["status"]): ManagerTeamAttendanceEntry => ({
  employee_id: "E", employee_name: "N", designation: "", clock_in: null, clock_out: null, status,
});

describe("teamBreakdown", () => {
  it("splits today's team by attendance status and keeps weekly offs in the total only", () => {
    const breakdown = teamBreakdown([entry("present"), entry("late"), entry("on_leave"), entry("absent"), entry("weekly_off"), entry("half_day")]);
    expect(breakdown).toMatchObject({ total: 6, present: 3, onLeave: 1, absent: 1, workFromHome: null });
  });

  it("is all zeros for a manager with no direct reports", () => {
    expect(teamBreakdown([])).toMatchObject({ total: 0, present: 0, onLeave: 0, absent: 0 });
  });
});

describe("donutArcs", () => {
  it("sizes each arc by its share and draws none for a figure with no source", () => {
    const arcs = donutArcs(teamBreakdown([entry("present"), entry("present"), entry("on_leave"), entry("absent")]), 50);
    const byKey = Object.fromEntries(arcs.map(arc => [arc.key, arc]));
    const circumference = 2 * Math.PI * 50;
    expect(Number.parseFloat(byKey.present.dash)).toBeCloseTo(circumference / 2);
    expect(Number.parseFloat(byKey.leave.dash)).toBeCloseTo(circumference / 4);
    expect(Number.parseFloat(byKey.wfh.dash)).toBe(0);
    expect(byKey.leave.offset).toBeCloseTo(-circumference / 2);
  });

  it("draws nothing for an empty team", () => {
    expect(donutArcs(teamBreakdown([]), 50).every(arc => Number.parseFloat(arc.dash) === 0)).toBe(true);
  });
});

const TEAM: KindCount[] = [
  { kind: "leave", pending: 3, needsMyAction: 3 },
  { kind: "expense", pending: 1, needsMyAction: 1 },
];

describe("team approvals", () => {
  it("lists only the workflows the manager may approve", () => {
    expect(teamApprovalRows(TEAM).map(row => [row.label, row.count, row.sub])).toEqual([
      ["Leave Requests", 3, "3 requests from your team"], ["Expense Requests", 1, "1 request from your team"],
    ]);
    expect(totalTeamPending(teamApprovalRows(TEAM))).toBe(4);
  });

  it("gives a dash (null) for a workflow the manager cannot approve", () => {
    expect(pendingFor(TEAM, "leave")).toBe(3);
    expect(pendingFor(TEAM, "wfh")).toBeNull();
  });
});

describe("waitingThisMonth", () => {
  const item = (kind: ApprovalKind, displayStatus: DisplayStatus, submittedAt: string): ApprovalItem => ({
    key: `${kind}:${submittedAt}`, kind, id: "1", employeeName: "A", employeeCode: "E", status: displayStatus, displayStatus,
    submittedAt, detailPrimary: "", detailSecondary: "", canAction: true, raw: {} as ApprovalItem["raw"],
  });

  it("counts only what is still waiting and was submitted this month", () => {
    const counts = waitingThisMonth(
      [item("leave", "pending", "2026-11-02T10:00:00Z"), item("leave", "pending", "2026-10-30T10:00:00Z"), item("leave", "approved", "2026-11-03T10:00:00Z"), item("wfh", "pending", "2026-11-04T10:00:00Z")],
      new Date("2026-11-05T12:00:00Z"),
    );
    expect(counts.leave).toBe(1);
    expect(counts.wfh).toBe(1);
    expect(counts.expense).toBe(0);
  });
});
