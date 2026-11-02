import { describe, expect, it } from "vitest";
import {
  additionsOutsideGross, adjustmentRows, componentRows, splitLop, wageSlipModel, wageSlipPeriodLabel,
  type PayslipAmounts,
} from "./payslipLayout";

const base: PayslipAmounts = {
  basic: "20000.00", hra: "10000.00", special_allowance: "5000.00", other_earnings: {},
  other_deductions: {}, bonus: "0.00", reimbursements: "0.00", gross_earnings: "35000.00",
  lop_deduction: "1346.15", pf_employee: "1800.00", esi_employee: "0.00", pt_deduction: "200.00",
  lwf_employee: "10.00", adjustments_earning: "0.00", adjustments_deduction: "0.00", adjustment_items: [],
  total_deductions: "3356.15", net_pay: "31643.85",
};

describe("splitLop", () => {
  it("totals exactly the full amount minus LOP, rounded", () => {
    const earned = splitLop([20000, 10000, 5000], 1346.15);
    expect(earned.reduce((a, b) => a + b, 0)).toBe(Math.round(35000 - 1346.15));
  });
  it("no LOP keeps the actual amounts", () => {
    expect(splitLop([13325, 899, 1110], 0)).toEqual([13325, 899, 1110]);
  });
  it("never goes below zero", () => {
    expect(splitLop([100, 50], 500)).toEqual([0, 0]);
  });
});

describe("wageSlipModel", () => {
  it("reconciles to the saved net pay", () => {
    const m = wageSlipModel(base, ["Food", "PF"]);
    expect(m.totals.actual).toBe(35000);
    expect(m.totals.earned).toBe(33654);
    expect(m.totals.deductions).toBeCloseTo(2010, 2);
    expect(m.totals.net).toBeCloseTo(31643.85, 2);
    // Earning − deductions shown = net (within the LOP rounding, under ₹1).
    expect(Math.abs(m.totals.earned - m.totals.deductions - m.totals.net)).toBeLessThan(1);
    // Fixed rows added once, as 0; PF not duplicated.
    expect(m.deductions.map(d => d.label)).toEqual(["PF", "PT", "ESIC", "LWF", "Food"]);
  });

  it("lists itemised adjustments and other components", () => {
    const m = wageSlipModel({
      ...base, lop_deduction: "0", other_earnings: { "Interim Bonus": 1110 }, gross_earnings: "36110.00",
      adjustments_earning: "500.00", adjustments_deduction: "150.00",
      adjustment_items: [
        { type: "arrear", label: "Arrear", amount: "500.00" },
        { type: "deduction", label: "Shoes", amount: "150.00" },
      ],
    });
    expect(m.earnings.map(e => e.label)).toEqual(["Basic", "HRA", "Special Allowance", "Interim Bonus", "Arrear"]);
    expect(m.earnings[4]).toEqual({ label: "Arrear", actual: null, earned: 500 });
    expect(m.deductions.at(-1)).toEqual({ label: "Shoes", amount: 150 });
  });
});

describe("adjustments", () => {
  it("older payslips without items show the saved totals", () => {
    const slip = { ...base, adjustments_deduction: "75.00", adjustments_earning: "200.00" };
    expect(adjustmentRows(slip, "deduction")).toEqual([{ label: "Other deductions", amount: 75 }]);
    expect(adjustmentRows(slip, "earning")).toEqual([{ label: "Additions", amount: 200 }]);
  });
  it("detects whether additions are already inside gross", () => {
    expect(additionsOutsideGross({ ...base, adjustments_earning: "500.00" })).toBe(true);
    expect(additionsOutsideGross({ ...base, adjustments_earning: "500.00", gross_earnings: "35500.00" })).toBe(false);
    expect(additionsOutsideGross(base)).toBe(false);
  });
  it("hides zero components except Basic", () => {
    expect(componentRows({ ...base, basic: "0", special_allowance: "0" }).map(r => r.label)).toEqual(["Basic", "HRA"]);
  });
});

describe("wageSlipPeriodLabel", () => {
  it("calendar month", () => {
    expect(wageSlipPeriodLabel("2026-09-01", "2026-09-30")).toBe("WAGES SLIP FOR THE MONTH OF SEPTEMBER-2026");
    expect(wageSlipPeriodLabel("2026-02-01", "2026-02-28")).toBe("WAGES SLIP FOR THE MONTH OF FEBRUARY-2026");
  });
  it("custom period", () => {
    expect(wageSlipPeriodLabel("2026-08-24", "2026-09-22")).toBe("WAGES SLIP FOR THE PERIOD 24 AUG-26 TO 22 SEP-26");
  });
});
