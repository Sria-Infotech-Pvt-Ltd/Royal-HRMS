import { describe, expect, it } from "vitest";
import {
  annualWarningTypes, creditYears, describeChange, projectedBalance, validateMonthlyCredit,
  type MonthlyImportRow, type MonthlyLeaveTypeRow,
} from "./monthlyLeave";

describe("validateMonthlyCredit", () => {
  it("accepts 0-31 with at most one decimal", () => {
    for (const ok of ["0", "1", "1.5", "31", " 2 "]) expect(validateMonthlyCredit(ok)).toBeNull();
  });

  it("rejects blank, negative, malformed and too-large values", () => {
    expect(validateMonthlyCredit("")).toMatch(/Enter/);
    expect(validateMonthlyCredit("-1")).toMatch(/negative/);
    expect(validateMonthlyCredit("1.25")).toMatch(/one decimal/);
    expect(validateMonthlyCredit("abc")).toMatch(/one decimal/);
    expect(validateMonthlyCredit("32")).toMatch(/exceed 31/);
  });
});

describe("projectedBalance", () => {
  const row: MonthlyLeaveTypeRow = {
    leave_type: "casual", leave_type_label: "Casual Leave", annual_days: 0, monthly_credit: 2,
    balance: { total: 10, used: 3, pending: 1, available: 7 },
  };

  it("applies only the difference from the current monthly credit", () => {
    expect(projectedBalance(row, 3)).toEqual({ delta: 1, total: 11, available: 8 });
    expect(projectedBalance(row, 0)).toEqual({ delta: -2, total: 8, available: 5 });
  });

  it("starts from zero when there is no balance yet", () => {
    expect(projectedBalance({ ...row, monthly_credit: 0, balance: null }, 1.5)).toEqual({ delta: 1.5, total: 1.5, available: 1.5 });
  });
});

describe("annualWarningTypes", () => {
  const base: MonthlyImportRow = {
    row: 2, employee_code: "E1", employee_name: "A", leave_type: "earned", leave_type_label: "Earned Leave",
    credit: 1, previous: 0, delta: 1, status: "new", message: "",
  };

  it("flags applied rows whose leave type also has an annual entitlement", () => {
    const rows = [base, { ...base, row: 3 }, { ...base, row: 4, leave_type: "casual", leave_type_label: "Casual Leave" }];
    expect(annualWarningTypes(rows, { earned: 15 })).toEqual(["Earned Leave (15 days/year)"]);
  });

  it("ignores rows that will not be applied", () => {
    expect(annualWarningTypes([{ ...base, status: "error" }, { ...base, status: "unchanged" }], { earned: 15 })).toEqual([]);
  });
});

describe("creditYears", () => {
  it("offers the current and two previous calendar years", () => {
    expect(creditYears(new Date(2026, 9, 14))).toEqual([2026, 2025, 2024]);
  });
});

describe("describeChange", () => {
  it("describes increases, decreases, removal and no change by the difference only", () => {
    expect(describeChange(2, 3)).toMatch(/2 → 3.*1 day\(s\) will be added/);
    expect(describeChange(3, 1)).toMatch(/3 → 1.*2 day\(s\) will be taken off/);
    expect(describeChange(2, 0)).toMatch(/Removes this month's credit: 2 day/);
    expect(describeChange(1.5, 1.5)).toBe("No change.");
    expect(describeChange(0.1, 0.3)).toMatch(/0.2 day/);
  });
});
