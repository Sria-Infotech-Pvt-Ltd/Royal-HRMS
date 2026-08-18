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
  | "assessments";

export const ALL_MODULES: ModuleKey[] = [
  "announcements", "recruitment", "face_attendance", "attendance", "leave",
  "payroll", "expenses", "separation", "voice_commands", "assessments",
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
};

export interface PlatformAdminInfo {
  id:        string;
  email:     string;
  full_name: string;
}

export type ProvisioningStatus = "pending" | "active" | "failed";

export interface Company {
  id:                    string;
  company_code:          string;
  company_name:          string;
  enabled_modules:       ModuleKey[];
  custom_domain:         string;
  is_active:             boolean;
  provisioning_status:   ProvisioningStatus;
  has_pending_password:  boolean;
  created_at:            string;
  updated_at:            string;
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
