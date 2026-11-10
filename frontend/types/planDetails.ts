// GET /settings/company/plan/ — Company Settings → Plan Details (read-only).
// Built by backend apps/tenants/customer_plan.py.

export type ModuleSource = "plan" | "dependency" | "added" | "removed" | "not_included";
export type ModuleAccess = "enabled" | "pending" | "off";
export type PlanPaymentStatus = "pending" | "paid" | "partially_paid" | "failed" | "waived";

export interface FeatureLabel { key: string; label: string; description: string }

export interface PlanModuleRow {
  key: string;
  label: string;
  description: string;
  category: string;
  /** Part of what the subscription entitles (plan + dependencies + company additions − removals). */
  included: boolean;
  /** What the company's users can use right now. */
  enabled: boolean;
  source: ModuleSource;
  access: ModuleAccess;
  required_by: string[];
}

export interface CurrentPlan {
  plan_name: string;
  plan_code: string;
  description: string;
  billing_period: string;
  starts_on: string | null;
  ends_on: string | null;
  period_ended: boolean;
  days_left: number | null;
  status: "active" | "inactive";
  activation: "active" | "awaiting_payment" | "setting_up";
  payment_status: PlanPaymentStatus;
  employee_count: number | null;
  price_per_employee: string;
  currency: string;
  gst_rate: string;
  gst_inclusive: boolean;
  total_amount: string | null;
  amount_paid: string;
  amount_pending_confirmation: string;
  amount_outstanding: string | null;
  features: FeatureLabel[];
}

export interface PlanPayment {
  paid_on: string;
  amount: string;
  currency: string;
  method: string;
  reference: string;
  status: "confirmed" | "awaiting_confirmation";
}

export interface PlanEstimate { billing_period: string; total: string; subtotal: string; gst_amount: string }

export interface OtherPlan {
  name: string;
  code: string;
  description: string;
  price_per_employee: string;
  currency: string;
  gst_rate: string;
  gst_inclusive: boolean;
  billing_periods: string[];
  min_employees: number | null;
  max_employees: number | null;
  modules: string[];
  additional_modules: string[];
  modules_not_included: string[];
  features: FeatureLabel[];
  estimate_employee_count: number | null;
  fits_employee_count: boolean;
  estimates: PlanEstimate[];
}

export interface PlanDetails {
  has_plan: boolean;
  current: CurrentPlan | null;
  modules: PlanModuleRow[];
  enabled_modules: string[];
  always_included: FeatureLabel[];
  coming_soon: FeatureLabel[];
  payments: PlanPayment[];
  other_plans: OtherPlan[];
}
