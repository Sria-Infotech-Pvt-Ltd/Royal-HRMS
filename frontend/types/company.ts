export type MonthName =
  | "January" | "February" | "March"     | "April"   | "May"      | "June"
  | "July"    | "August"   | "September" | "October" | "November" | "December";

// GET/PUT /api/settings/company/financial-year/ — the FY label fields are
// always pre-formatted by the backend ("FY 2026-27") and relative to today's
// date at request time; the frontend never recomputes them.
export interface FinancialYearConfig {
  financial_year_start_month: MonthName;
  previous_financial_year:    string;
  current_financial_year:     string;
  next_financial_year:        string;
}

export interface FinancialYearUpdateInput {
  financial_year_start_month: MonthName;
}

// ─── Company Profile ──────────────────────────────────────────────────────────

export type Jurisdiction = "india" | "foreign";

export interface CompanyData {
  id?: number;
  jurisdiction: Jurisdiction;
  entity_type: string;
  company_name: string;
  trade_name: string;
  logo_url?: string | null;
  date_of_incorporation: string;
  is_listed: boolean;
  holding_company_info: string;
  cin: string;
  roc_jurisdiction: string;
  pan: string;
  tan: string;
  country_of_registration: string;
  registration_number: string;
  ein: string;
  udyam_msme: string;
  msme_class: string;
  iec: string;
  epfo_code: string;
  esic_code: string;
  professional_tax_reg: string;
  signatory_full_name: string;
  signatory_designation: string;
  signatory_din_pan: string;
  signatory_email: string;
  signatory_appears_on_invoices: boolean;
  bank_account_holder: string;
  bank_account_number: string;
  bank_ifsc: string;
  bank_account_type: string;
  industry: string;
  nic_code: string;
  nature_of_business: string;
  address: string;
  city: string;
  state: string;
  pin_code: string;
  communication_address_same_as_registered: boolean;
  communication_address: string;
  communication_city: string;
  communication_state: string;
  communication_pin_code: string;
  default_currency: string;
  date_format: string;
  timezone: string;
  financial_year_start_month: MonthName;
  primary_email: string;
  website: string;
  official_phone: string;
  updated_at?: string;
}

export type CompanyFieldErrors = Partial<Record<keyof CompanyData, string>>;

export interface CompanySectionProps {
  form: CompanyData;
  errors: CompanyFieldErrors;
  canEdit: boolean;
  onFieldChange: (key: keyof CompanyData, value: string | boolean) => void;
}

export interface GSTRegistration {
  id: string;
  company: number;
  gstin: string;
  state: string;
  registration_type: string;
  place_of_business: string;
  created_at: string;
  updated_at: string;
}

export interface GSTRegistrationPayload {
  gstin: string;
  state: string;
  registration_type: string;
  place_of_business: string;
}

export interface Director {
  id: string;
  company: number;
  din: string;
  name: string;
  designation: string;
  created_at: string;
  updated_at: string;
}

export interface DirectorPayload {
  din: string;
  name: string;
  designation: string;
}
