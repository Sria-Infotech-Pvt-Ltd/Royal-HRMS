// Tax declaration (investment declaration) — API shapes and the form's own state.
// The items employees can declare and their limits come from the server
// (GET /payroll/tax-declarations/schema/) so the form, the validation and the TDS
// estimate always use the same definitions.

export type TaxRegime = "old" | "new";
export type TaxDeclarationStatus = "draft" | "submitted" | "approved";

export interface TaxSchemaField {
  key: string;
  label: string;
  /** What document the employee will be asked for as proof. */
  proof: string;
  cap: number | null;
}

export interface TaxSchemaGroup {
  key: string;
  title: string;
  hint: string | null;
  /** Combined limit across all the group's fields, if it has one. */
  cap: number | null;
  fields: TaxSchemaField[];
}

export interface TaxDeclarationSchema {
  groups: TaxSchemaGroup[];
  landlord_relationships: { value: string; label: string }[];
  landlord_pan_threshold: number;
  /** Cities where the HRA exemption is 50% of basic (40% elsewhere). */
  metro_cities: string[];
  senior_cap: number;
  standard_cap: number;
}

export interface TaxRentDetails {
  monthly_rent: number;
  months: number;
  metro: boolean;
  landlord_name: string;
  landlord_address: string;
  landlord_pan: string;
  landlord_relationship: string;
}

export interface TaxPreviousEmployer {
  name: string;
  income: number;
  tds: number;
}

export interface TaxHomeLoanDetails {
  lender_name: string;
  lender_pan: string;
}

export interface TaxDeclarationDetails {
  hra?: TaxRentDetails;
  home_loan?: TaxHomeLoanDetails;
  senior_self_family?: boolean;
  senior_parents?: boolean;
  previous_employer?: TaxPreviousEmployer;
}

/** `declared_investments` is a flat item -> rupee amount map plus the reserved `_details` object. */
export type TaxDeclaredInvestments = { [itemKey: string]: number | TaxDeclarationDetails | undefined; _details?: TaxDeclarationDetails };

export interface ApiTaxDeclaration {
  id: string;
  employee_name: string;
  financial_year_start: number;
  financial_year: string;
  tax_regime: TaxRegime;
  tax_regime_display: string;
  declared_investments: TaxDeclaredInvestments;
  /** What each head is worth after the statutory limits (old regime), in rupees. */
  deduction_summary: Record<string, number>;
  status: TaxDeclarationStatus;
  status_display: string;
  submitted_at: string | null;
  approved_at: string | null;
  approved_by_name: string;
}

/** Text-box state of the declaration form — numbers stay strings while typing. */
export interface TaxFormState {
  regime: TaxRegime;
  amounts: Record<string, string>;
  isSeniorSelfFamily: boolean;
  isSeniorParents: boolean;
  rent: {
    monthlyRent: string;
    months: string;
    isMetro: boolean;
    landlordName: string;
    landlordAddress: string;
    landlordPan: string;
    landlordRelationship: string;
  };
  previousEmployer: { name: string; income: string; tds: string };
  homeLoan: { lenderName: string; lenderPan: string };
}

/** One claimed item that proof can be uploaded for. */
export interface TaxProofItem {
  key: string;
  label: string;
  /** Rupees claimed against the item. */
  declared: number;
  /** What actually counts after the statutory limit (limits come from the server's schema, never hard-coded here). */
  eligible: number;
  /** What document payroll will ask for. */
  proof: string;
  /** Whether a policy / account / receipt number is worth asking for. */
  asksReference: boolean;
}
