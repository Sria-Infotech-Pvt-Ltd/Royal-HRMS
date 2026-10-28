// Salary Setup (Payroll > Salary Setup): employees together with their salary record, and the counts shown in the KPI
// cards. Both come from the server, which uses the same "payroll ready" definition as the dashboards.

export type SalarySetupState = "configured" | "scheduled" | "missing";
export type SalarySetupFilter = "all" | "configured" | "missing" | "ready" | "blocked";

export interface SalarySetupRecord {
  id: string;
  annual_ctc: string;
  monthly_ctc: string;
  effective_from: string;
  salary_structure: string | null;
  structure_name: string | null;
  reason_note: string;
}

export interface SalarySetupRow {
  uuid: string;
  employee_id: string;
  full_name: string;
  department: string;
  branch: string;
  salary: SalarySetupRecord | null;
  /** configured: a current record; scheduled: a record that starts in the future; missing: none. */
  state: SalarySetupState;
  payroll_ready: boolean;
  /** Why this employee is not payroll ready (empty when ready). */
  blockers: string[];
}

export interface SalarySetupPage {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: SalarySetupRow[];
}

export interface SalarySetupSummary {
  total: number;
  configured: number;
  scheduled: number;
  missing: number;
  payroll_ready: number;
  blocked: number;
  blocked_by: { no_salary_record: number; no_salary_structure: number; no_bank_details: number };
  /** What "payroll ready" requires, in plain words. */
  requirements: string[];
}
