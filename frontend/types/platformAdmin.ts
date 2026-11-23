// Module keys must match backend/apps/tenants/models.py ALL_MODULES exactly.
export type ModuleKey =
  | "announcements"
  | "recruitment"
  | "face_attendance"
  | "attendance"
  | "leave"
  | "payroll"
  | "expenses"
  | "separation"
  | "voice_commands"
  | "assessments"
  | "documents"
  | "assets"
  | "wfh"
  | "training";

export const ALL_MODULES: ModuleKey[] = [
  "announcements", "recruitment", "face_attendance", "attendance", "leave",
  "payroll", "expenses", "separation", "voice_commands", "assessments",
  "documents", "assets", "wfh", "training",
];

export const MODULE_LABELS: Record<ModuleKey, string> = {
  announcements:   "Announcements",
  recruitment:     "Recruitment",
  face_attendance: "Face ID Attendance",
  attendance:      "Attendance",
  leave:           "Leave Management",
  payroll:         "Payroll",
  expenses:        "Expenses",
  separation:      "Separation & Offboarding",
  voice_commands:  "Voice Commands",
  assessments:     "Assessments",
  documents:       "Document Management",
  assets:          "Asset Management",
  wfh:             "Work From Home",
  training:        "Training & Learning",
};

// ── SaaS ───────────────────────────────────────────────────────────────────

export type FeatureKind = "core" | "module" | "display" | "coming_soon";

export interface SaasFeature {
  key: string;
  label: string;
  category: string;
  kind: FeatureKind;
  /** One-line description (also shown to companies in Settings → Plan Details). */
  description?: string;
  depends_on: string[];
}

export type PlanStatus = "draft" | "active" | "inactive";

export interface SubscriptionPlan {
  id: string;
  code: string;
  name: string;
  description: string;
  price_per_employee: string;
  currency: string;
  billing_periods: ("monthly" | "yearly")[];
  gst_rate: string;
  gst_inclusive: boolean;
  min_employees: number | null;
  max_employees: number | null;
  /** Feature keys (module + display kinds). */
  features: string[];
  /** Module keys the plan switches on (features + dependencies). */
  modules: string[];
  status: PlanStatus;
  is_public: boolean;
  display_order: number;
  is_legacy: boolean;
  subscriber_count: number;
  updated_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompanySubscription {
  id: string;
  client_id: string;
  plan: string;
  plan_code: string;
  plan_name: string;
  source: "manual" | "website" | "legacy";
  status: "active" | "inactive";
  starts_on: string;
  ends_on: string | null;
  employee_count: number | null;
  billing_period: string;
  price_per_employee: string;
  currency: string;
  gst_rate: string;
  gst_inclusive: boolean;
  max_employees: number | null;
  plan_features: string[];
  extra_modules: string[];
  removed_modules: string[];
  modules: string[];
  notes: string;
  payment_status: PaymentStatus;
  amount_due: string | null;
  amount_received: string;
  /** Recorded but not yet confirmed (not counted as received). */
  amount_pending_confirmation: string;
  /** Still to collect (amount_due − confirmed, never below 0); "0.00" when waived; null when amount_due is unknown. */
  amount_outstanding: string | null;
  amount_overpaid: string;
  unconfirmed_payments: number;
  payment_waiver_reason: string;
  provisioning_status: SubscriptionProvisioning;
  provisioning_error: string;
  provisioned_at: string | null;
  /** The plan was edited after this subscription's snapshot (applied on "Apply latest plan"). */
  plan_outdated: boolean;
  latest_plan: { modules: string[]; price_per_employee: string; currency: string; gst_rate: string;
                 gst_inclusive: boolean; max_employees: number | null } | null;
  created_at: string;
  updated_at: string;
}

export interface PlanChangePreview {
  from_plan: string;
  to_plan: string;
  same_plan: boolean;
  modules: string[];
  difference: { added: string[]; removed: string[] };
  pricing: null | {
    employee_count: number;
    billing_period: string;
    from: { plan: string; price_per_employee: string; currency: string; amount_due: string | null };
    to: { plan: string; price_per_employee: string; currency: string; months: number; subtotal: string;
          gst_rate: string; gst_inclusive: boolean; gst_amount: string; amount_due: string };
  };
}

/** Edit Subscription preview (POST …/edit/ with dry_run). */
export interface SubscriptionEditPreview {
  changes: { field: string; label: string; from: string | number | null; to: string | number | null }[];
  plan_changed: boolean;
  amount: {
    from: string | null;
    to: string | null;
    mode: "auto" | "manual" | "unchanged";
    reason: string;
    calculated: null | {
      employee_count: number; billing_period: string; months: number; price_per_employee: string; currency: string;
      subtotal: string; gst_rate: string; gst_inclusive: boolean; gst_amount: string; total: string;
    };
  };
  payments: { received: string; pending: string; outstanding_before: string | null; outstanding_after: string | null; overpaid_after: string };
  payment_status: { from: PaymentStatus; to: PaymentStatus };
  modules: { added: string[]; removed: string[] };
  warnings: string[];
}

export type PaymentStatus = "pending" | "paid" | "partially_paid" | "failed" | "waived";
export type SubscriptionProvisioning = "awaiting_payment" | "pending" | "success" | "failed";
export type PaymentMethod = "upi" | "bank_transfer" | "neft" | "rtgs" | "cash" | "cheque" | "other";

export interface SubscriptionPaymentRecord {
  id: string;
  amount: string;
  currency: string;
  method: PaymentMethod;
  method_label: string;
  paid_on: string;
  reference: string;
  notes: string;
  has_receipt: boolean;
  receipt_name: string;
  status: "recorded" | "verified" | "rejected";
  rejection_reason: string;
  recorded_by_name: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface CustomerRow {
  id: string;
  company_code: string;
  company_name: string;
  contact_name: string;
  contact_phone: string;
  expected_employee_count: number | null;
  is_active: boolean;
  provisioning_status: ProvisioningStatus;
  enabled_modules: string[];
  /** Modules the company's users can actually use (login / API gate). */
  effective_modules?: string[];
  created_at: string;
  subscription: CompanySubscription | null;
}

export interface SubscriptionHistoryEntry {
  id: string;
  company_code: string;
  company_name: string;
  event: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  note: string;
  admin_name: string | null;
  created_at: string;
}

export interface SaasDashboard {
  plans_total: number;
  plans_active: number;
  plans_public: number;
  customers_total: number;
  customers_without_subscription: number;
  subscriptions_active: number;
  subscriptions_inactive: number;
  provisioning_failed: number;
  by_source: Record<string, number>;
  by_plan: { plan_name: string; customers: number }[];
  registrations_pending_approval: number;
  registrations_awaiting_payment: number;
  registrations_rejected: number;
  registrations_paid: number;
}

export interface PaymentTransaction {
  gateway: string;
  order_id: string;
  payment_id: string | null;
  amount_minor: number;
  currency: string;
  status: string;
  failure_reason: string;
  created_at: string;
}

export interface CompanyRegistration {
  id: string;
  reference: string;
  company_name: string;
  company_code: string;
  contact_name: string;
  admin_email: string;
  contact_phone: string;
  address: string;
  gstin: string;
  employee_count: number;
  plan: string;
  plan_code: string;
  plan_name: string;
  billing_period: string;
  price_per_employee: string;
  months: number;
  subtotal: string;
  gst_rate: string;
  gst_inclusive: boolean;
  gst_amount: string;
  total: string;
  currency: string;
  payment_status: "pending" | "paid" | "failed" | "refunded";
  paid_at: string | null;
  approval_status: "pending" | "approved" | "rejected";
  rejection_reason: string;
  refund_status: string;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  client_id: string | null;
  provisioning_status: ProvisioningStatus | null;
  modules: string[];
  payments: PaymentTransaction[];
  created_at: string;
}

export interface PlatformNotification {
  id: string;
  kind: string;
  title: string;
  message: string;
  link: string;
  is_read: boolean;
  created_at: string;
}

export interface PlatformAdminInfo {
  id:        string;
  email:     string;
  full_name: string;
}

export type ProvisioningStatus = "pending" | "active" | "failed" | "awaiting";

export interface Company {
  id:                       string;
  company_code:             string;
  company_name:             string;
  enabled_modules:          ModuleKey[];
  is_active:                boolean;
  provisioning_status:      ProvisioningStatus;
  contact_name:             string;
  contact_phone:            string;
  address:                  string;
  gstin:                    string;
  expected_employee_count:  number | null;
  contract_start_date:      string | null;
  has_pending_password:     boolean;
  created_at:               string;
  updated_at:               string;
}

export interface CompanyListResponse {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     Company[];
}

export interface CreateCompanyInput {
  company_code: string;
  company_name: string;
  admin_email:  string;
  modules?:     ModuleKey[] | null;
  contact_name?:             string;
  contact_phone?:            string;
  address?:                  string;
  gstin?:                    string;
  expected_employee_count?:  number | null;
  contract_start_date?:      string | null;
}

export interface CreateCompanyResult {
  client: Company;
}

export interface PlatformSMTPSettings {
  host:          string;
  port:          number;
  username:      string;
  use_tls:       boolean;
  from_email:    string;
  sender_name:   string;
  is_configured: boolean;
  updated_at:    string;
}

export interface PlatformSMTPSettingsInput {
  host:        string;
  port:        number;
  username:    string;
  password?:   string;
  use_tls:     boolean;
  from_email:  string;
  sender_name: string;
}

export interface PlatformAdminAccount {
  id:         string;
  email:      string;
  full_name:  string;
  is_active:  boolean;
  last_login: string | null;
  created_at: string;
}

export interface PlatformAdminAccountListResponse {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     PlatformAdminAccount[];
}

export interface PlatformAdminInviteInput {
  email:     string;
  full_name: string;
}

export interface AuditLogEntry {
  id:                  string;
  admin_email:         string;
  action:              string;
  target_company_code: string;
  changes:             Record<string, unknown>;
  ip_address:          string | null;
  created_at:          string;
}

export interface AuditLogListResponse {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     AuditLogEntry[];
}

export interface CompanyUsage {
  company_code:      string;
  company_name:      string;
  employee_count:    number;
  last_activity_at:  string | null;
}

export interface DashboardStats {
  total_companies:    number;
  active_companies:   number;
  disabled_companies: number;
  provisioning: {
    pending: number;
    active:  number;
    failed:  number;
  };
  module_adoption:      Record<ModuleKey, number>;
  recent_companies:     Company[];
  company_usage:        CompanyUsage[];
  dormant_company_count: number;
}
