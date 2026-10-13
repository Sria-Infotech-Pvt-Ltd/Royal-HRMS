import { describe, expect, it } from "vitest";
import {
  buildDeclaredInvestments, emptyFormState, fieldCap, formStateFromDeclaration, groupTotals, validateRent,
} from "./taxDeclarationForm";
import type { ApiTaxDeclaration, TaxDeclarationSchema } from "@/types/taxDeclaration";

const SCHEMA: TaxDeclarationSchema = {
  groups: [
    { key: "80c", title: "80C", hint: null, cap: 150000, fields: [
      { key: "80C_PPF", label: "PPF", proof: "", cap: null }, { key: "80C_ELSS", label: "ELSS", proof: "", cap: null },
    ] },
  ],
  landlord_relationships: [{ value: "none", label: "Not related" }],
  landlord_pan_threshold: 100000,
  metro_cities: ["Delhi"],
  senior_cap: 50000,
  standard_cap: 25000,
};

function declaration(declaredInvestments: ApiTaxDeclaration["declared_investments"]): ApiTaxDeclaration {
  return {
    id: "1", employee_name: "A", financial_year_start: 2026, financial_year: "2026-27", tax_regime: "old",
    tax_regime_display: "Old Regime", declared_investments: declaredInvestments, deduction_summary: {},
    status: "draft", status_display: "Draft", submitted_at: null, approved_at: null, approved_by_name: "",
  };
}

describe("buildDeclaredInvestments", () => {
  it("sends only the amounts that were filled in", () => {
    const state = emptyFormState();
    state.amounts = { "80C_PPF": "50000", "80C_ELSS": "", "80E": "0" };
    expect(buildDeclaredInvestments(state, null)).toEqual({ "80C_PPF": 50000 });
  });

  it("includes rent details with an upper-cased landlord PAN", () => {
    const state = emptyFormState();
    state.rent = { ...state.rent, monthlyRent: "20000", landlordName: " Asha ", landlordAddress: "1 Road", landlordPan: "abcde1234f", isMetro: true };
    const payload = buildDeclaredInvestments(state, null);
    expect(payload._details?.hra).toMatchObject({ monthly_rent: 20000, months: 12, metro: true, landlord_name: "Asha", landlord_pan: "ABCDE1234F" });
  });

  it("keeps an older self-computed HRA exemption until rent is entered", () => {
    expect(buildDeclaredInvestments(emptyFormState(), declaration({ HRA: 60000 }))).toEqual({ HRA: 60000 });
    const state = emptyFormState();
    state.rent.monthlyRent = "10000";
    expect(buildDeclaredInvestments(state, declaration({ HRA: 60000 })).HRA).toBeUndefined();
  });
});

describe("formStateFromDeclaration", () => {
  it("moves the old single 80C and 80D totals into the nearest itemised field", () => {
    const state = formStateFromDeclaration(declaration({ "80C": 100000, "80D": 15000 }));
    expect(state.amounts).toEqual({ "80C_OTHER": "100000", "80D_SELF_FAMILY": "15000" });
    expect(state.regime).toBe("old");
  });
});

describe("limits", () => {
  it("counts only up to the group limit", () => {
    const state = emptyFormState();
    state.amounts = { "80C_PPF": "100000", "80C_ELSS": "80000" };
    expect(groupTotals(SCHEMA.groups[0], state)).toEqual({ declared: 180000, counted: 150000 });
  });

  it("raises the 80D limit for senior citizens", () => {
    const state = emptyFormState();
    expect(fieldCap("80D_PARENTS", SCHEMA, state)).toBe(25000);
    state.isSeniorParents = true;
    expect(fieldCap("80D_PARENTS", SCHEMA, state)).toBe(50000);
  });
});

describe("validateRent", () => {
  it("needs a landlord PAN above one lakh a year only", () => {
    const state = emptyFormState();
    state.rent = { ...state.rent, monthlyRent: "8000", landlordName: "A", landlordAddress: "B" };
    expect(validateRent(state, SCHEMA)).toBeNull();
    state.rent.monthlyRent = "9000";
    expect(validateRent(state, SCHEMA)).toMatch(/PAN is required/);
    state.rent.landlordPan = "ABCDE1234F";
    expect(validateRent(state, SCHEMA)).toBeNull();
  });

  it("does nothing when no rent is declared", () => {
    expect(validateRent(emptyFormState(), SCHEMA)).toBeNull();
  });
});
