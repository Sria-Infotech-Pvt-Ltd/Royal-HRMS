// Assign CTC → employee-wise salary components: client-side helpers.
// The backend (apps/payroll/services_salary_components.py) validates and
// calculates everything; these only shape rows and give early feedback.

import type { SalaryComponentInput, SalaryComponentRole, SalaryPreviewRow } from "@/types/payroll";

export const COMPONENT_TYPE_LABEL: Record<SalaryComponentInput["component_type"], string> = {
  earning: "Earning", allowance: "Allowance", deduction: "Deduction",
};

export const CALCULATION_LABEL: Record<SalaryComponentInput["calculation_type"], string> = {
  percentage_of_ctc: "% of CTC", percentage_of_basic: "% of Basic", fixed: "Fixed (monthly ₹)",
};

export const ROLE_LABEL: Record<SalaryComponentRole, string> = {
  basic: "Basic", hra: "HRA", special_allowance: "Special Allowance", other: "Other",
};

/** Strip preview-only fields so rows can be sent back as the component list. */
export function toInputs(rows: SalaryPreviewRow[]): SalaryComponentInput[] {
  return rows.map(r => ({
    source_component: r.source_component, name: r.name, component_type: r.component_type,
    calculation_type: r.calculation_type, role: r.role, value: r.value, order: r.order,
    is_taxable: r.is_taxable, is_enabled: r.is_enabled,
  }));
}

export function blankComponent(order: number): SalaryComponentInput {
  return {
    source_component: null, name: "", component_type: "allowance", calculation_type: "fixed",
    role: "other", value: "0", order, is_taxable: true, is_enabled: true,
  };
}

/** Problems worth showing before asking the server (it re-checks everything). */
export function quickCheck(rows: SalaryComponentInput[]): string[] {
  const errors: string[] = [];
  const seen = new Set<string>();
  rows.forEach((r, i) => {
    const name = r.name.trim();
    if (!name) errors.push(`Row ${i + 1}: name is required.`);
    else if (seen.has(name.toLowerCase())) errors.push(`"${name}" appears more than once.`);
    seen.add(name.toLowerCase());
    const v = Number(r.value);
    if (r.value.trim() === "" || !Number.isFinite(v)) errors.push(`${name || `Row ${i + 1}`}: value must be a number.`);
    else if (v < 0) errors.push(`${name || `Row ${i + 1}`}: value cannot be negative.`);
  });
  const enabled = rows.filter(r => r.is_enabled);
  (["basic", "hra", "special_allowance"] as const).forEach(role => {
    if (enabled.filter(r => r.role === role).length > 1) errors.push(`Only one enabled component can be ${ROLE_LABEL[role]}.`);
  });
  return errors;
}

/** Previous vs proposed monthly amount per component name (union of both lists). */
export function compareRows(previous: SalaryPreviewRow[], proposed: SalaryPreviewRow[]) {
  const prev = new Map(previous.filter(r => r.is_enabled).map(r => [r.name, Number(r.monthly_amount)]));
  const next = new Map(proposed.filter(r => r.is_enabled).map(r => [r.name, Number(r.monthly_amount)]));
  const names = [...new Set([...prev.keys(), ...next.keys()])];
  return names.map(name => ({
    name,
    previous: prev.get(name) ?? null,
    proposed: next.get(name) ?? null,
    change: (next.get(name) ?? 0) - (prev.get(name) ?? 0),
  }));
}

export type MessageArea = "details" | "components" | "summary";

/**
 * Which section of the Assign CTC modal a server/client message belongs to,
 * so it is shown next to what it is about. Display only — the text is unchanged.
 */
export function messageArea(text: string): MessageArea {
  const t = text.toLowerCase();
  if (t.includes("effective date") || t.includes("finalised") || t.includes("current revision")
    || t.includes("no salary structure applies") || t.includes("annual ctc must")) return "details";
  if (t.includes("do not equal the annual ctc") || t.includes("no basic component")) return "summary";
  return "components";
}
