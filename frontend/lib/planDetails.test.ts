import { describe, expect, it } from "vitest";
import { comparisonRows, enabledOutsidePlan, moduleLabels, moduleSummary, periodLabel, sourceNote } from "./planDetails";
import type { PlanDetails, PlanModuleRow } from "@/types/planDetails";

const row = (key: string, extra: Partial<PlanModuleRow> = {}): PlanModuleRow => ({
  key, label: key.toUpperCase(), description: "", category: "X", included: false, enabled: false,
  source: "not_included", access: "off", required_by: [], ...extra,
});

const details = (modules: PlanModuleRow[], other: PlanDetails["other_plans"] = [], hasPlan = true): PlanDetails => ({
  has_plan: hasPlan, current: null, modules, enabled_modules: modules.filter(m => m.enabled).map(m => m.key),
  always_included: [], coming_soon: [], payments: [], other_plans: other,
});

const plan = (code: string, modules: string[]) => ({
  name: code, code, description: "", price_per_employee: "1", currency: "INR", gst_rate: "18", gst_inclusive: false,
  billing_periods: ["monthly"], min_employees: null, max_employees: null, modules, additional_modules: [],
  modules_not_included: [], features: [], estimate_employee_count: null, fits_employee_count: true, estimates: [],
});

describe("module rows", () => {
  it("explains dependencies", () => {
    expect(sourceNote(row("attendance", { source: "dependency", required_by: ["Payroll"] }))).toBe("Required by Payroll");
    expect(sourceNote(row("payroll", { source: "plan" }))).toBe("");
  });

  it("flags modules on but outside the plan only when a plan exists", () => {
    const r = row("wfh", { enabled: true, included: false });
    expect(enabledOutsidePlan(r, true)).toBe(true);
    expect(enabledOutsidePlan(r, false)).toBe(false);
  });

  it("summarises included, enabled, pending and not included", () => {
    expect(moduleSummary([
      row("a", { included: true, enabled: true, access: "enabled" }),
      row("b", { included: true, access: "pending" }),
      row("c"),
    ])).toEqual({ included: 2, enabled: 1, pending: 1, notIncluded: 1 });
  });
});

describe("plan comparison", () => {
  it("lists modules in the current plan or any other plan", () => {
    const d = details([row("payroll", { included: true }), row("assets"), row("voice")], [plan("pro", ["payroll", "assets"])]);
    expect(comparisonRows(d)).toEqual([
      { key: "payroll", label: "PAYROLL", current: true, plans: { pro: true } },
      { key: "assets", label: "ASSETS", current: false, plans: { pro: true } },
    ]);
  });

  it("without a plan, compares against the enabled modules", () => {
    const d = details([row("leave", { enabled: true })], [plan("basic", [])], false);
    expect(comparisonRows(d)[0]).toMatchObject({ key: "leave", current: true });
  });

  it("labels keys from the server rows", () => {
    expect(moduleLabels(details([row("assets")]), ["assets", "unknown"])).toEqual(["ASSETS", "unknown"]);
    expect([periodLabel("monthly"), periodLabel("yearly"), periodLabel("")]).toEqual(["Monthly", "Yearly", "Not set"]);
  });
});
