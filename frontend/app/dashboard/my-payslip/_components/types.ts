// Shared types for the ESS Payslips screen. Mirrors exactly what the
// backend's EmployeePayslipSerializer / MyProfileSerializer / PayrollSettingsSerializer
// / EmployeeTaxDeclaration serializer return — no field here is invented.

export interface ApiPayslip {
  id: string;
  cycle: string;
  cycle_start: string;
  cycle_end: string;
  pay_date: string;
  employee_name: string;
  employee_id_code: string;
  department: string;
  branch: string;
  annual_ctc: string;
  monthly_ctc: string;
  basic: string;
  hra: string;
  special_allowance: string;
  other_earnings: Record<string, number>;
  reimbursements: string;
  bonus: string;
  gross_earnings: string;
  total_working_days: number;
  lop_days: string;
  lop_deduction: string;
  pf_employee: string;
  pf_employer: string;
  esi_employee: string;
  esi_employer: string;
  pt_deduction: string;
  lwf_employee: string;
  lwf_employer: string;
  income_tax: string;
  adjustments_earning: string;
  adjustments_deduction: string;
  total_deductions: string;
  net_pay: string;
  status: string;
  payslip_pdf: string | null;
  sent_at: string | null;
  paid_at: string | null;
  open_query_count: number;
}

export interface ApiMe {
  full_name: string;
  employee_id: string;
  department: string;
  designation: string;
  date_of_joining: string | null;
  profile?: {
    bank_name?: string;
    account_number?: string;
    ifsc_code?: string;
    pf_number?: string;
  };
}

// Only the field this screen needs — the full PayrollSettings record has many
// more (cycle days, EPF/ESI rates for HR config screens, etc).
export interface ApiPayrollSettings {
  gratuity_rate: string;
}

// Only the fields this screen needs from EmployeeTaxDeclaration (see TaxTab.tsx
// for the full shape) — used solely to show the real FY label + review status
// in the "tax declaration window" side note.
export interface ApiTaxDeclarationBrief {
  financial_year: string;
  status: "draft" | "submitted" | "approved";
}

// From GET /settings/company/financial-year/ (CompanyFinancialYearView) —
// the company's actually-configured FY start month (default "April"), so
// this screen's YTD range isn't hardcoded to the calendar-April assumption.
export interface ApiFinancialYearConfig {
  financial_year_start_month: string;
  current_financial_year: string;
}

export interface PagedResponse<T> { results: T[]; count: number; }

export const INR = (n: string | number): string =>
  "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });

export const fmtMonth = (d: string): string =>
  new Date(d).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

const MONTH_NAMES = [
  "january", "february", "march", "april", "may", "june",
  "july", "august", "september", "october", "november", "december",
];

// Returns the FY start date for "today", using the company's configured FY
// start month (apps.accounts.models.Company.financial_year_start_month —
// "April" by default, but admin-editable) rather than assuming April.
export function currentFinancialYearStart(startMonthName: string, today: Date = new Date()): Date {
  const monthIndex = MONTH_NAMES.indexOf(startMonthName.trim().toLowerCase());
  const startMonth = monthIndex >= 0 ? monthIndex : 3;
  const year = today.getMonth() >= startMonth ? today.getFullYear() : today.getFullYear() - 1;
  return new Date(year, startMonth, 1);
}

export function financialYearLabel(fyStart: Date): string {
  return `FY ${fyStart.getFullYear()}–${String(fyStart.getFullYear() + 1).slice(-2)}`;
}

export function fyEndLabel(fyStart: Date): string {
  // Day 0 of (start month, next year) = the last day of the month before —
  // i.e. one full year after fyStart, minus a day. Generalises correctly
  // regardless of which month the company's FY actually starts in.
  const fyEnd = new Date(fyStart.getFullYear() + 1, fyStart.getMonth(), 0);
  return fyEnd.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
}

export interface YtdSummary {
  gross: number;
  net: number;
  incomeTax: number;
  periodCount: number;
  monthRangeLabel: string;
}

// Payslips already come back ordered -cycle_start (most recent first) from
// MyPayslipsView, so the current FY's rows are always within the first
// page's 20 most-recent results — no separate aggregate endpoint needed.
export function computeYtd(payslips: ApiPayslip[], fyStart: Date): YtdSummary {
  const inFy = payslips.filter(p => new Date(p.cycle_start) >= fyStart);
  const gross = inFy.reduce((sum, p) => sum + Number(p.gross_earnings), 0);
  const net = inFy.reduce((sum, p) => sum + Number(p.net_pay), 0);
  const incomeTax = inFy.reduce((sum, p) => sum + Number(p.income_tax ?? 0), 0);
  const monthRangeLabel = inFy.length === 0
    ? financialYearLabel(fyStart)
    : `${fmtMonth(inFy[inFy.length - 1].cycle_start)} – ${fmtMonth(inFy[0].cycle_start)}`;
  return { gross, net, incomeTax, periodCount: inFy.length, monthRangeLabel };
}
