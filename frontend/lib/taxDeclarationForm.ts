// Pure helpers behind the tax declaration form: loading a saved declaration into
// text-box state, turning the state back into the API payload, and the checks that
// can be done before the server is asked.

import type {
  ApiTaxDeclaration, TaxDeclarationDetails, TaxDeclarationSchema, TaxDeclaredInvestments, TaxFormState, TaxProofItem, TaxSchemaGroup,
} from "@/types/taxDeclaration";

const PAN_PATTERN = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
const LEGACY_80C_KEY = "80C";
const LEGACY_80D_KEY = "80D";
const LEGACY_HRA_KEY = "HRA";
const FALLBACK_ITEM_FOR_LEGACY_80C = "80C_OTHER";
const FALLBACK_ITEM_FOR_LEGACY_80D = "80D_SELF_FAMILY";

export function parseAmount(text: string): number {
  const value = Number(text);
  return Number.isFinite(value) && value > 0 ? value : 0;
}

function numberText(value: unknown): string {
  return typeof value === "number" && value > 0 ? String(value) : "";
}

export function emptyFormState(): TaxFormState {
  return {
    regime: "new",
    amounts: {},
    isSeniorSelfFamily: false,
    isSeniorParents: false,
    rent: { monthlyRent: "", months: "12", isMetro: false, landlordName: "", landlordAddress: "", landlordPan: "", landlordRelationship: "none" },
    previousEmployer: { name: "", income: "", tds: "" },
    homeLoan: { lenderName: "", lenderPan: "" },
  };
}

/** Declarations saved before the itemised form kept one 80C and one 80D total — show them in the nearest item. */
export function formStateFromDeclaration(declaration: ApiTaxDeclaration | null): TaxFormState {
  const state = emptyFormState();
  if (!declaration) return state;
  state.regime = declaration.tax_regime;

  const saved = declaration.declared_investments;
  for (const [key, value] of Object.entries(saved)) {
    if (typeof value === "number" && value > 0) state.amounts[key] = String(value);
  }
  const legacy80C = saved[LEGACY_80C_KEY];
  if (typeof legacy80C === "number" && legacy80C > 0) {
    state.amounts[FALLBACK_ITEM_FOR_LEGACY_80C] = String(parseAmount(state.amounts[FALLBACK_ITEM_FOR_LEGACY_80C] ?? "") + legacy80C);
    delete state.amounts[LEGACY_80C_KEY];
  }
  const legacy80D = saved[LEGACY_80D_KEY];
  if (typeof legacy80D === "number" && legacy80D > 0) {
    state.amounts[FALLBACK_ITEM_FOR_LEGACY_80D] = String(parseAmount(state.amounts[FALLBACK_ITEM_FOR_LEGACY_80D] ?? "") + legacy80D);
    delete state.amounts[LEGACY_80D_KEY];
  }

  const details = saved._details;
  if (details) {
    state.isSeniorSelfFamily = details.senior_self_family === true;
    state.isSeniorParents = details.senior_parents === true;
    if (details.hra) {
      state.rent = {
        monthlyRent: numberText(details.hra.monthly_rent),
        months: String(details.hra.months || 12),
        isMetro: details.hra.metro,
        landlordName: details.hra.landlord_name,
        landlordAddress: details.hra.landlord_address,
        landlordPan: details.hra.landlord_pan,
        landlordRelationship: details.hra.landlord_relationship || "none",
      };
    }
    if (details.home_loan) {
      state.homeLoan = { lenderName: details.home_loan.lender_name, lenderPan: details.home_loan.lender_pan };
    }
    if (details.previous_employer) {
      state.previousEmployer = {
        name: details.previous_employer.name,
        income: numberText(details.previous_employer.income),
        tds: numberText(details.previous_employer.tds),
      };
    }
  }
  return state;
}

/** The old self-computed HRA exemption is kept until the employee enters rent details instead. */
export function legacyHraExemption(declaration: ApiTaxDeclaration | null): number {
  const value = declaration?.declared_investments[LEGACY_HRA_KEY];
  return typeof value === "number" ? value : 0;
}

export function buildDeclaredInvestments(state: TaxFormState, declaration: ApiTaxDeclaration | null): TaxDeclaredInvestments {
  const payload: TaxDeclaredInvestments = {};
  for (const [key, text] of Object.entries(state.amounts)) {
    const amount = parseAmount(text);
    if (amount > 0) payload[key] = amount;
  }

  const details: TaxDeclarationDetails = {};
  const monthlyRent = parseAmount(state.rent.monthlyRent);
  if (monthlyRent > 0) {
    details.hra = {
      monthly_rent: monthlyRent,
      months: Number(state.rent.months) || 12,
      metro: state.rent.isMetro,
      landlord_name: state.rent.landlordName.trim(),
      landlord_address: state.rent.landlordAddress.trim(),
      landlord_pan: state.rent.landlordPan.trim().toUpperCase(),
      landlord_relationship: state.rent.landlordRelationship,
    };
  } else {
    const legacy = legacyHraExemption(declaration);
    if (legacy > 0) payload[LEGACY_HRA_KEY] = legacy;
  }
  if (parseAmount(state.amounts["24B"] ?? "") > 0) {
    details.home_loan = { lender_name: state.homeLoan.lenderName.trim(), lender_pan: state.homeLoan.lenderPan.trim().toUpperCase() };
  }
  if (state.isSeniorSelfFamily) details.senior_self_family = true;
  if (state.isSeniorParents) details.senior_parents = true;

  const previousIncome = parseAmount(state.previousEmployer.income);
  const previousTds = parseAmount(state.previousEmployer.tds);
  if (previousIncome > 0 || previousTds > 0 || state.previousEmployer.name.trim()) {
    details.previous_employer = { name: state.previousEmployer.name.trim(), income: previousIncome, tds: previousTds };
  }
  if (Object.keys(details).length > 0) payload._details = details;
  return payload;
}

/** Sum of what the employee typed in a group, and what will actually count after its combined limit. */
export function groupTotals(group: TaxSchemaGroup, state: TaxFormState): { declared: number; counted: number } {
  const declared = group.fields.reduce((sum, field) => sum + parseAmount(state.amounts[field.key] ?? ""), 0);
  return { declared, counted: group.cap !== null ? Math.min(declared, group.cap) : declared };
}

/** The effective limit on one field (the 80D ones depend on the senior-citizen answers). */
export function fieldCap(fieldKey: string, schema: TaxDeclarationSchema, state: TaxFormState): number | null {
  if (fieldKey === "80D_SELF_FAMILY") return state.isSeniorSelfFamily ? schema.senior_cap : schema.standard_cap;
  if (fieldKey === "80D_PARENTS") return state.isSeniorParents ? schema.senior_cap : schema.standard_cap;
  for (const group of schema.groups) {
    const field = group.fields.find(candidate => candidate.key === fieldKey);
    if (field) return field.cap;
  }
  return null;
}

/** Home loan interest needs the lender's name and PAN (Form 124). */
export function validateHomeLoan(state: TaxFormState): string | null {
  if (parseAmount(state.amounts["24B"] ?? "") === 0) return null;
  if (!state.homeLoan.lenderName.trim()) return "Enter your home loan lender's name.";
  const pan = state.homeLoan.lenderPan.trim().toUpperCase();
  if (!pan) return "Enter your home loan lender's PAN.";
  if (!PAN_PATTERN.test(pan)) return "Lender PAN must look like ABCDE1234F.";
  return null;
}

/** Returns the first problem the employee can fix before sending, or null. Mirrors the server's rent checks. */
export function validateRent(state: TaxFormState, schema: TaxDeclarationSchema): string | null {
  const monthlyRent = parseAmount(state.rent.monthlyRent);
  if (monthlyRent === 0) return null;
  const months = Number(state.rent.months);
  if (!Number.isInteger(months) || months < 1 || months > 12) return "Months of rent must be between 1 and 12.";
  if (!state.rent.landlordName.trim()) return "Enter your landlord's name for the rent you are claiming.";
  if (!state.rent.landlordAddress.trim()) return "Enter your landlord's address for the rent you are claiming.";
  const pan = state.rent.landlordPan.trim().toUpperCase();
  if (pan && !PAN_PATTERN.test(pan)) return "Landlord PAN must look like ABCDE1234F.";
  if (monthlyRent * months > schema.landlord_pan_threshold && !pan) {
    return "Landlord PAN is required when your yearly rent is above ₹1,00,000.";
  }
  return null;
}

/** Heads in the order the summary lists them, with the label an employee recognises. */
export const DEDUCTION_HEAD_LABELS: { key: string; label: string }[] = [
  { key: "HRA", label: "HRA exemption (house rent)" },
  { key: "80C", label: "Section 80C investments" },
  { key: "80CCD1B", label: "Section 80CCD(1B) additional NPS" },
  { key: "80D", label: "Section 80D health insurance" },
  { key: "24B", label: "Section 24(b) home loan interest" },
  { key: "80E", label: "Section 80E education loan interest" },
  { key: "80G", label: "Section 80G donations" },
];

/** Total deduction a declaration earns after limits — only the old regime can claim any. */
export function totalDeduction(declaration: ApiTaxDeclaration): number {
  if (declaration.tax_regime !== "old") return 0;
  return Object.values(declaration.deduction_summary).reduce((sum, amount) => sum + amount, 0);
}

const LEGACY_PROOF_LABELS: Record<string, string> = {
  "80C": "Section 80C investments", "80D": "Section 80D health insurance", HRA: "House rent (HRA)",
};
const RENT_PROOF = "Rent receipts or rent agreement";

/** The items an old-regime employee has claimed, i.e. what proof can be uploaded for. */
export function proofItems(declaration: ApiTaxDeclaration, schema: TaxDeclarationSchema): TaxProofItem[] {
  if (declaration.tax_regime !== "old") return [];
  const items: TaxProofItem[] = [];
  const saved = declaration.declared_investments;

  const rent = saved._details?.hra;
  const legacyRent = legacyHraExemption(declaration);
  if (rent) items.push({ key: "HRA", label: LEGACY_PROOF_LABELS.HRA, declared: rent.monthly_rent * rent.months, proof: RENT_PROOF, asksReference: false });
  else if (legacyRent > 0) items.push({ key: "HRA", label: LEGACY_PROOF_LABELS.HRA, declared: legacyRent, proof: RENT_PROOF, asksReference: false });

  for (const group of schema.groups) {
    for (const field of group.fields) {
      const declared = saved[field.key];
      if (typeof declared === "number" && declared > 0) items.push({ key: field.key, label: field.label, declared, proof: field.proof, asksReference: true });
    }
  }
  for (const key of ["80C", "80D"]) {
    const declared = saved[key];
    if (typeof declared === "number" && declared > 0) items.push({ key, label: LEGACY_PROOF_LABELS[key], declared, proof: "Relevant receipt or statement", asksReference: true });
  }
  return items;
}
