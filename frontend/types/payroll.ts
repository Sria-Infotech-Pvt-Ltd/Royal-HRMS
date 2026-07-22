export interface PayrollSettings {
  id: string;
  cycle_start_day: number;
  cycle_end_day: number;
  pay_day: number;
  approval_levels: "L1" | "L1_L2";
  employee_query_window_hours: number;
  enable_reimbursements: boolean;
  enable_bonuses: boolean;
  created_at: string;
  updated_at: string;
}

export interface SalaryComponent {
  id: string;
  name: string;
  component_type: "earning" | "deduction" | "allowance";
  calculation_type: "percentage_of_ctc" | "percentage_of_basic" | "fixed";
  value: string;
  is_taxable: boolean;
  is_active: boolean;
  order: number;
  created_at: string;
  updated_at: string;
}

export interface SalaryStructure {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  is_active: boolean;
  components: SalaryComponent[];
  created_at: string;
  updated_at: string;
}

export interface SalaryStructureListItem {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StatutoryConfig {
  id: string;
  state: string;
  state_name: string;
  state_code: string;
  pt_applicable: boolean;
  pt_slabs: { min: number; max: number | null; amount: number }[];
  esi_applicable: boolean;
  esi_wage_ceiling: string;
  esi_employee_rate: string;
  esi_employer_rate: string;
  lwf_applicable: boolean;
  lwf_employee_amount: string;
  lwf_employer_amount: string;
  lwf_frequency: "monthly" | "halfyearly" | "annual";
  created_at: string;
  updated_at: string;
}

export interface BranchPayrollConfig {
  id: string;
  branch: string;
  branch_name: string;
  branch_state: string;
  salary_structure: string | null;
  structure_name: string | null;
  pf_applicable: boolean;
  pf_employee_rate: string;
  pf_employer_rate: string;
  pf_wage_ceiling: string;
  created_at: string;
  updated_at: string;
}

export interface EmployeeSalaryConfig {
  id: string;
  employee: string;
  employee_name: string;
  employee_id_code: string;
  annual_ctc: string;
  monthly_ctc: string;
  salary_structure: string | null;
  structure_name: string | null;
  effective_from: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PayrollCycle {
  id: string;
  cycle_start: string;
  cycle_end: string;
  pay_date: string;
  status: string;
  created_by: string;
  created_by_name: string;
  l1_approver_name: string | null;
  l2_approver_name: string | null;
  attendance_l1_approved_at: string | null;
  attendance_l2_approved_at: string | null;
  query_window_closes_at: string | null;
  paid_at: string | null;
  cancelled_at: string | null;
  cancelled_by: string | null;
  cancelled_by_name: string | null;
  cancellation_reason: string;
  notes: string;
  payslip_count: number;
  created_at: string;
  updated_at: string;
}

export interface EmployeePayslip {
  id: string;
  cycle: string;
  employee: string;
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
  bonus_breakdown: BonusEntry[];
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
  total_deductions: string;
  net_pay: string;
  status: "draft" | "sent" | "acknowledged" | "queried" | "resolved" | "paid";
  payslip_pdf: string | null;
  sent_at: string | null;
  query_deadline: string | null;
  paid_at: string | null;
  open_query_count: number;
  created_at: string;
  updated_at: string;
}

export interface PayslipQuery {
  id: string;
  payslip: string;
  raised_by: string;
  raised_by_name: string;
  description: string;
  status: "open" | "resolved";
  resolved_by: string | null;
  resolved_by_name: string | null;
  resolution_note: string;
  created_at: string;
  updated_at: string;
}

export interface BonusEntry {
  type: string;
  amount: string;
  note: string;
}

export interface ExpenseItem {
  id: string;
  title: string;
  category: string;
  amount: string;
  expense_date: string;
  already_included: boolean;
}

export interface EmployeeExpenseSummary {
  payslip_id: string;
  employee_id: string;
  employee_name: string;
  employee_code: string;
  current_reimbursements: string;
  expenses: ExpenseItem[];
}

export interface ReferralBonusItem {
  id: string;
  bonus_amount: string;
  candidate_name: string;
}

export interface EmployeeReferralSummary {
  payslip_id: string;
  employee_id: string;
  employee_name: string;
  employee_code: string;
  referral_bonuses: ReferralBonusItem[];
}
