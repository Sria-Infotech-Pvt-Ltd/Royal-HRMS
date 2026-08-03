"use client";

// Single source of truth for "which year" across every module (Leave
// Allocation, Carry Forward, Attendance, Payroll, Reports, ...) instead of
// each one defaulting to the calendar year independently. Backed by
// GET /api/settings/company/financial-year/ — the backend computes and
// caches the FY labels (24h), so this is safe to call on every page load.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { FinancialYearConfig as FinancialYearApiConfig, MonthName } from "@/types/company";

export const MONTH_NAMES: MonthName[] = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export interface FiscalYearConfig {
  startMonth:    MonthName | null;
  currentLabel:  string | null; // e.g. "FY 2026-27"
  previousLabel: string | null;
  nextLabel:     string | null;
  currentYear:   number;        // parsed from currentLabel — for consumers that need a raw ?year= param
  previousYear:  number;
  nextYear:      number;
  loading:       boolean;
  error:         string | null;
}

// Extracts the label's start year, e.g. "FY 2026-27" -> 2026. Labels are
// opaque strings from the backend — this is display-agnostic parsing, not a
// recomputation of the financial year itself.
function parseStartYear(label: string | null | undefined): number | null {
  if (!label) return null;
  const match = label.match(/(\d{4})/);
  return match ? Number(match[1]) : null;
}

// Leave balances/requests are keyed by plain calendar year on the backend —
// LeaveBalance.year is set from the joining/request date's .year directly,
// and the annual reset Celery task runs every Jan 1, not on the company's
// fiscal-year start month. Querying leave endpoints with the fiscal year's
// start year instead (e.g. via useFiscalYearConfig().currentYear) silently
// returns empty data for however many months precede the fiscal year's
// start month each year. Use this instead for anything under /leave/.
export function getLeaveYear(): number {
  return new Date().getFullYear();
}

export function useFiscalYearConfig(): FiscalYearConfig {
  const { data, loading, error } = useFetch<FinancialYearApiConfig>(API.settings.financialYear);

  // Falls back to the plain calendar year while the request is in flight or
  // if it fails, so every consumer keeps working exactly as before until the
  // real config loads — never blocks on this.
  const fallbackYear = new Date().getFullYear();
  const currentYear   = parseStartYear(data?.current_financial_year)  ?? fallbackYear;
  const previousYear  = parseStartYear(data?.previous_financial_year) ?? currentYear - 1;
  const nextYear       = parseStartYear(data?.next_financial_year)     ?? currentYear + 1;

  return {
    startMonth:    data?.financial_year_start_month ?? null,
    currentLabel:  data?.current_financial_year ?? null,
    previousLabel: data?.previous_financial_year ?? null,
    nextLabel:     data?.next_financial_year ?? null,
    currentYear,
    previousYear,
    nextYear,
    loading,
    error,
  };
}
