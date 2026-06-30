import type { PayrollEmployee } from "./payrollData";

export interface SalaryComponent {
  key: keyof PayrollEmployee;
  label: string;
  category: "earning" | "deduction";
  enabled: boolean;
  statutory: boolean;
  basis: string;
}

export const SALARY_COMPONENTS: SalaryComponent[] = [
  // ── Earnings ─────────────────────────────────────────────────────────────────
  { key: "basic",    label: "Basic Salary",     category: "earning",   enabled: true,  statutory: false, basis: "40% of CTC"     },
  { key: "hra",      label: "HRA",              category: "earning",   enabled: true,  statutory: false, basis: "50% of Basic"   },
  { key: "da",       label: "Dearness Allow.",  category: "earning",   enabled: true,  statutory: false, basis: "15% of Basic"   },
  { key: "special",  label: "Special Allow.",   category: "earning",   enabled: true,  statutory: false, basis: "10% of Basic"   },
  { key: "ot",       label: "Overtime",         category: "earning",   enabled: true,  statutory: false, basis: "Per OT Hour"    },
  // ── Deductions ───────────────────────────────────────────────────────────────
  { key: "pf",       label: "Provident Fund",   category: "deduction", enabled: true,  statutory: true,  basis: "12% of Basic"   },
  { key: "esi",      label: "ESI",              category: "deduction", enabled: true,  statutory: true,  basis: "0.75% of Gross" },
  { key: "pt",       label: "Professional Tax", category: "deduction", enabled: true,  statutory: true,  basis: "Fixed / Month"  },
  { key: "tds",      label: "Income Tax (TDS)", category: "deduction", enabled: true,  statutory: true,  basis: "Annual Slab"    },
  { key: "loan_emi", label: "Loan EMI",         category: "deduction", enabled: true,  statutory: false, basis: "Per Loan"       },
  { key: "advance",  label: "Salary Advance",   category: "deduction", enabled: true,  statutory: false, basis: "Per Recovery"   },
  { key: "lop",      label: "Loss of Pay",      category: "deduction", enabled: true,  statutory: false, basis: "Per Day"        },
];

export const EARNING_COMPONENTS   = SALARY_COMPONENTS.filter(c => c.category === "earning"   && c.enabled);
export const DEDUCTION_COMPONENTS = SALARY_COMPONENTS.filter(c => c.category === "deduction" && c.enabled);
