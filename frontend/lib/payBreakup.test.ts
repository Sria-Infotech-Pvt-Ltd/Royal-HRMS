import { describe, expect, it } from "vitest";
import { buildPay, type PayStructureComponent } from "./payBreakup";

const MONTHLY_CTC = 100_000;

function component(overrides: Partial<PayStructureComponent> & Pick<PayStructureComponent, "code" | "name" | "calculation_type" | "value">): PayStructureComponent {
  return {
    id: overrides.code, component_type: "earning", is_taxable: true, is_active: true, order: 0,
    effective_from: "2026-01-01", reset_override: false, ...overrides,
  };
}

const BASIC = component({ code: "BASIC", name: "Basic", calculation_type: "percentage_of_ctc", value: "40", order: 10 });
const HRA = component({ code: "HRA", name: "HRA", calculation_type: "percentage_of_basic", value: "40", order: 20 });
const CONVEYANCE = component({ code: "CONVEYANCE", name: "Conveyance Allowance", calculation_type: "fixed", value: "1600", order: 30 });
const SPECIAL = component({ code: "SPECIAL", name: "Special Allowance", calculation_type: "balance_to_ctc", value: "0", order: 40 });

const earningNames = (components: PayStructureComponent[], overrides = {}) =>
  buildPay(MONTHLY_CTC, { components, overrides }).earnings.map(line => line.name);

describe("Basic pay breakup from a salary structure", () => {
  it("shows only the components the structure has, in its order", () => {
    expect(earningNames([SPECIAL, HRA, BASIC])).toEqual(["Basic", "HRA", "Special Allowance"]);
  });

  it("hides a disabled component and leaves it out of the totals", () => {
    const withConveyance = buildPay(MONTHLY_CTC, { components: [BASIC, HRA, CONVEYANCE, SPECIAL] });
    const disabled = buildPay(MONTHLY_CTC, { components: [BASIC, HRA, { ...CONVEYANCE, is_active: false }, SPECIAL] });
    expect(withConveyance.earnings.map(line => line.name)).toContain("Conveyance Allowance");
    expect(disabled.earnings.map(line => line.name)).not.toContain("Conveyance Allowance");
    expect(disabled.gross).toBeGreaterThan(0);
  });

  it("never invents the old fixed list when the structure has no components", () => {
    const pay = buildPay(MONTHLY_CTC, { components: [] });
    expect(pay.earnings).toEqual([]);
    expect(earningNames([BASIC])).not.toContain("Medical Allowance");
    expect(earningNames([BASIC])).not.toContain("Leave Travel Allowance");
  });

  it("follows the structure's rules: % of CTC, % of Basic and balancing to CTC", () => {
    const pay = buildPay(MONTHLY_CTC, { components: [BASIC, HRA, SPECIAL] });
    const amountOf = (name: string) => pay.earnings.find(line => line.name === name)?.amount;
    expect(amountOf("Basic")).toBe(40_000);
    expect(amountOf("HRA")).toBe(16_000);
    // The balancing component fills what is left of the CTC after the employer contributions.
    expect(pay.monthlyCtc).toBeCloseTo(MONTHLY_CTC, -1);
    expect(amountOf("Special Allowance")).toBeGreaterThan(0);
  });

  it("ignores an override stored for a component the structure does not have", () => {
    const withStale = buildPay(MONTHLY_CTC, { components: [BASIC, HRA, SPECIAL], overrides: { conv: 5000 } });
    const without = buildPay(MONTHLY_CTC, { components: [BASIC, HRA, SPECIAL] });
    expect(withStale.gross).toBe(without.gross);
    expect(withStale.earnings.map(line => line.name)).not.toContain("Conveyance Allowance");
  });

  it("still applies an override to a component the structure has", () => {
    const pay = buildPay(MONTHLY_CTC, { components: [BASIC, HRA, SPECIAL], overrides: { HRA: 10_000 } });
    expect(pay.earnings.find(line => line.name === "HRA")?.amount).toBe(10_000);
  });

  it("keeps the statutory employer contributions alongside the structure's earnings", () => {
    const pay = buildPay(MONTHLY_CTC, { components: [BASIC, HRA, SPECIAL] });
    expect(pay.employer.map(line => line.name)).toContain("Employer PF (EPF)");
    expect(pay.deductions.map(line => line.name)).toContain("Employee PF");
  });
});
