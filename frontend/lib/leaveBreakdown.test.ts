import { describe, expect, it } from "vitest";
import { monthTotals, scheduleLabel, signed, typesWithBreakdown } from "./leaveBreakdown";
import type { LeaveBalance } from "@/types/employeeDashboard";

const base: LeaveBalance = { leave_type: "casual", total_days: 12, used_days: 2, remaining: 10, carried_forward: 0 };

describe("monthTotals", () => {
  it("sums recorded credits, adjustments and usage without float drift", () => {
    expect(monthTotals([
      { month: 1, label: "Jan 2026", monthly_credit: 1, other_adjustments: 0.1, used: 0.5 },
      { month: 2, label: "Feb 2026", monthly_credit: 1.5, other_adjustments: 0.2, used: 0 },
    ])).toEqual({ monthly_credit: 2.5, other_adjustments: 0.3, used: 0.5 });
    expect(monthTotals([])).toEqual({ monthly_credit: 0, other_adjustments: 0, used: 0 });
  });
});

describe("typesWithBreakdown", () => {
  it("keeps only leave types with month rows and tolerates older payloads without `monthly`", () => {
    const withRows = { ...base, monthly: { months: [{ month: 1, label: "Jan 2026", monthly_credit: 1, other_adjustments: 0, used: 0 }], used_not_itemised: 0 } };
    const empty = { ...base, leave_type: "sick", monthly: { months: [], used_not_itemised: 0 } };
    expect(typesWithBreakdown([withRows, empty, { ...base, leave_type: "earned" }]).map(b => b.leave_type)).toEqual(["casual"]);
  });
});

describe("scheduleLabel", () => {
  it("describes the configured schedule, defaulting to annual", () => {
    expect(scheduleLabel(base)).toBe("Credited annually");
    expect(scheduleLabel({ ...base, credit_schedule: "monthly", monthly_carry_forward: true })).toBe("Credited monthly · carries forward");
    expect(scheduleLabel({ ...base, credit_schedule: "monthly", monthly_carry_forward: false })).toBe("Credited monthly · no carry forward");
  });
});

describe("signed", () => {
  it("prefixes positive adjustments with +", () => {
    expect([signed(1.5), signed(-2), signed(0)]).toEqual(["+1.5", "-2", "0"]);
  });
});

describe("typesWithBreakdown with statements", () => {
  it("includes monthly-schedule types that only carry a statement", () => {
    const stmtOnly = {
      ...base, leave_type: "pink",
      statement: { opening: 0, adjustments: 0, used_not_itemised: 0, total_pending: 0, reconciled: true,
        months: [{ month: 3, label: "Mar 2026", carry_off: true, closed: true, carried_in: 0, credit: 1,
                   used: 0, pending: 0, expired: 1, credit_left: 0, closing: 0 }] },
    };
    expect(typesWithBreakdown([stmtOnly, base]).map(b => b.leave_type)).toEqual(["pink"]);
  });
});
