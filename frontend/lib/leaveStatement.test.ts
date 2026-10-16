import { describe, expect, it } from "vitest";
import { defaultMonth, monthLines, monthOf, scheduleChip, splitBySchedule, statementNotes } from "./leaveStatement";
import type { LeaveStatement, LeaveStatementMonth } from "@/types/employeeDashboard";

const month = (over: Partial<LeaveStatementMonth> = {}): LeaveStatementMonth => ({
  month: 3, label: "Mar 2026", carry_off: false, closed: true, carried_in: 0, credit: 1,
  used: 0, pending: 0, expired: 0, credit_left: 0, closing: 1, ...over,
});

const stmt = (over: Partial<LeaveStatement> = {}): LeaveStatement => ({
  opening: 0, adjustments: 0, used_not_itemised: 0, months: [month()], total_pending: 0, reconciled: true,
  total_credited: 1, total_expired: 0, monthly_carry_forward: true, monthly_rules_from: "2026-01-01", ...over,
});

describe("monthLines", () => {
  it("shows backend values only, with expiry just for no-carry months", () => {
    expect(monthLines(month()).map(l => l.key)).toEqual(["credit", "used", "closing"]);
    const off = monthLines(month({ carry_off: true, expired: 1, closing: 0 }));
    expect(off.map(l => [l.key, l.value])).toEqual([["credit", 1], ["used", 0], ["expired", 1], ["closing", 0]]);
    expect(off.find(l => l.key === "expired")?.tone).toBe("error");
  });

  it("adds carried-in and pending only when present", () => {
    const keys = monthLines(month({ carried_in: 2, pending: 0.5, closing: 2.5 })).map(l => l.key);
    expect(keys).toEqual(["carried_in", "credit", "used", "pending", "closing"]);
  });

  it("renders a month with no credit record", () => {
    expect(monthLines(month({ credit: 0, closing: 0 })).map(l => [l.key, l.value]))
      .toEqual([["credit", 0], ["used", 0], ["closing", 0]]);
  });
});

describe("statementNotes", () => {
  it("explains missing credits, non-expiring opening and pending month-end processing", () => {
    const notes = statementNotes(stmt({ months: [month({ credit: 0 })], opening: 2, reconciled: false }), 2026);
    expect(notes.some(n => n.includes("No monthly credits are recorded for 2026"))).toBe(true);
    expect(notes.some(n => n.includes("2 day(s)") && n.includes("never expire"))).toBe(true);
    expect(notes.some(n => n.includes("Month-end processing"))).toBe(true);
  });

  it("mentions when the current rules started mid-year", () => {
    expect(statementNotes(stmt({ monthly_rules_from: "2026-11-01" }), 2026).join(" ")).toMatch(/apply from 1 Nov 2026/);
    expect(statementNotes(stmt({ monthly_rules_from: "2026-01-01" }), 2026)).toEqual([]);
  });
});

describe("scheduleChip", () => {
  it("describes the configured carry-forward", () => {
    expect(scheduleChip(stmt())).toMatch(/carries forward/);
    expect(scheduleChip(stmt({ monthly_carry_forward: false }))).toMatch(/expires at month end/);
  });
});

describe("splitBySchedule", () => {
  it("separates by the policy's schedule and keeps unknown schedules apart", () => {
    const rows = [
      { leave_type: "earned", credit_schedule: "annual" },
      { leave_type: "pink", credit_schedule: "monthly" },
      { leave_type: "orphan", credit_schedule: null },
      { leave_type: "old_cache" },
    ];
    const s = splitBySchedule(rows);
    expect(s.annual.map(r => r.leave_type)).toEqual(["earned"]);
    expect(s.monthly.map(r => r.leave_type)).toEqual(["pink"]);
    expect(s.unclassified.map(r => r.leave_type)).toEqual(["orphan", "old_cache"]);
  });
});

describe("defaultMonth / monthOf", () => {
  const today = new Date(2026, 9, 16);
  it("picks the current, last or first month by year", () => {
    expect([defaultMonth(2026, today), defaultMonth(2025, today), defaultMonth(2027, today)]).toEqual([10, 12, 1]);
  });
  it("returns the backend month row, or null when the month isn't in the statement", () => {
    const s = stmt({ months: [month({ month: 3 })] });
    expect(monthOf(s, 3)?.label).toBe("Mar 2026");
    expect(monthOf(s, 4)).toBeNull();
    expect(monthOf(null, 3)).toBeNull();
  });
});
