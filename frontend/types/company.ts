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
