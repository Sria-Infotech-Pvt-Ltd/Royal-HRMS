import { describe, expect, it } from "vitest";
import { blankComponent, compareRows, quickCheck, toInputs } from "./salaryComponents";
import type { SalaryComponentInput, SalaryPreviewRow } from "@/types/payroll";

const row = (over: Partial<SalaryComponentInput> = {}): SalaryComponentInput => ({
  source_component: "tmpl-1", name: "Basic", component_type: "earning", calculation_type: "percentage_of_ctc",
  role: "basic", value: "40", order: 1, is_taxable: true, is_enabled: true, ...over,
});
const preview = (name: string, monthly: string, over: Partial<SalaryPreviewRow> = {}): SalaryPreviewRow => ({
  ...row({ name, role: "other" }), monthly_amount: monthly, annual_amount: String(Number(monthly) * 12), ...over,
});

describe("salary component helpers", () => {
  it("strips preview-only amounts before sending rows back", () => {
    const [r] = toInputs([preview("Basic", "20000.00")]);
    expect(r).not.toHaveProperty("monthly_amount");
    expect(r).not.toHaveProperty("annual_amount");
    expect(r.name).toBe("Basic");
  });

  it("new rows are employee-only (no template link) and enabled", () => {
    expect(blankComponent(5)).toMatchObject({ source_component: null, order: 5, is_enabled: true, role: "other" });
  });

  it("flags blank names, duplicates (any case), bad numbers and repeated Basic", () => {
    expect(quickCheck([row()])).toEqual([]);
    expect(quickCheck([row({ name: " " })])).toEqual(["Row 1: name is required."]);
    expect(quickCheck([row(), row({ name: "BASIC", role: "other" })])).toContain('"BASIC" appears more than once.');
    expect(quickCheck([row({ value: "abc" })])).toContain("Basic: value must be a number.");
    expect(quickCheck([row({ value: "-1" })])).toContain("Basic: value cannot be negative.");
    expect(quickCheck([row(), row({ name: "Basic 2" })])).toContain("Only one enabled component can be Basic.");
    expect(quickCheck([row(), row({ name: "Basic 2", is_enabled: false })])).toEqual([]);
  });

  it("compares current and proposed monthly amounts by component", () => {
    const out = compareRows(
      [preview("Basic", "20000"), preview("HRA", "10000")],
      [preview("Basic", "24000"), preview("Conveyance", "1600"), preview("HRA", "0", { is_enabled: false })],
    );
    expect(out).toEqual([
      { name: "Basic", previous: 20000, proposed: 24000, change: 4000 },
      { name: "HRA", previous: 10000, proposed: null, change: -10000 },
      { name: "Conveyance", previous: null, proposed: 1600, change: 1600 },
    ]);
  });
});
