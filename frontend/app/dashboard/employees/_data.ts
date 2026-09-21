// ============================================================
//  Employees feature — types, mock data, section configs, helpers
//  Frontend-only. Swap MOCK_EMPLOYEES for an API call when the
//  backend is ready (see fetchEmployees / fetchEmployee stubs).
// ============================================================

import type { OnboardingFieldConfigByStep } from "@/types/onboardingFieldConfig";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import { STATES } from "@/app/dashboard/settings/company/_data";

export type EmployeeStatus = "active" | "onboarding" | "inactive";

// Widens the status FILTER dropdown's value beyond the per-row
// EmployeeStatus above (which stays active/onboarding/inactive, unchanged)
// — "probation" and "notice_period" are real, separately-filterable
// backend buckets (EmployeeListCreateView.get()'s status_param) that don't
// have their own per-row status value since the table shows them via
// employmentStatus / the Notice Period pill instead.
export type EmployeeStatusFilter = EmployeeStatus | "probation" | "notice_period";
export type Gender = "male" | "female" | "transgender";

/** A single field's value bag — every detail value lives here keyed by FieldDef.key */
export type DetailValues = Record<string, string>;

/** One repeatable row inside a table-type section (Family, Academic, …) */
export interface TableRow {
  _id: string;
  [key: string]: string;
}

export interface Employee {
  id: string;            // route id (== employee code), e.g. "RSS00001D"
  uuid?: string;         // backend UUID — used for API calls (activate/deactivate etc.)
  code: string;
  firstName: string;
  middleName: string;
  lastName: string;
  email: string;
  phone: string;
  department: string;
  designation: string;
  dateOfJoining: string; // ISO yyyy-mm-dd
  dateOfBirth: string;   // ISO yyyy-mm-dd
  location: string;
  gender: Gender;
  status: EmployeeStatus;
  /** "probation" | "confirmed" — flipped exactly once by the Confirmation action. */
  employmentStatus: string;
  confirmationDate: string | null;
  /** Reporting manager's name, or null for a top-level role (shown as "CEO Office"). */
  reportingManagerName?: string | null;
  /** Set only while a separation is in progress — drives the "Notice Period" pill/column. */
  lastWorkingDay?: string | null;
  /** Current OrgUnit name (e.g. "AI & ML") — the real hierarchy node, distinct from the legacy `department` string. */
  orgUnitName?: string | null;
  /** Immediate parent OrgUnit name (e.g. "Software Services"), shown as gray subtext under orgUnitName. */
  orgUnitParentName?: string | null;
  /** all the long-tail profile fields, keyed by FieldDef.key */
  details: DetailValues;
  /** repeatable sections, keyed by TableSection.id */
  tables: Record<string, TableRow[]>;
  /** real uploaded documents from the API */
  documents?: DocEntry[];
}

// ────────────────────────────────────────────────────────────
//  Field + section config (drives the whole profile form, DRY)
// ────────────────────────────────────────────────────────────

export type FieldType =
  | "text" | "email" | "tel" | "number"
  | "select" | "date" | "radio" | "textarea" | "readonly" | "file" | "checkbox";

export interface FieldOption { value: string; label: string; }

export interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  readOnly?: boolean;
  options?: FieldOption[];
  placeholder?: string;
  full?: boolean; // span both columns
}

export interface GridSection {
  id: string;
  label: string;
  icon: string;
  kind: "grid";
  fields: FieldDef[];
}
export interface TableColumn {
  key: string;
  label: string;
  type?: FieldType;
  options?: FieldOption[];
  placeholder?: string;
}
export interface TableSection {
  id: string;
  label: string;
  icon: string;
  kind: "table";
  description?: string;
  addLabel: string;
  columns: TableColumn[];
}
export type DocStatus = "verified" | "pending" | "not-uploaded";
export interface DocEntry {
  name: string;
  documentType: string; // backend EmployeeDocument.document_type choice value
  required: boolean;
  status?: DocStatus;
  uploadedOn?: string;
  fileUrl?: string;
  fileName?: string;
  fileSize?: number;
}

/** Raw document shape returned by the employee-detail and document-upload APIs. */
export interface ApiDocument {
  id: number;
  document_type: string;
  document_type_display: string;
  file: string;
  file_name: string;
  file_size: number;
  uploaded_at: string;
}

export interface DocSection {
  id: string;
  label: string;
  icon: string;
  kind: "docs";
  variant?: "cards" | "table";
  documents: DocEntry[];
}
export type ProfileSection = GridSection | TableSection | DocSection;

// ── shared option sets ──────────────────────────────────────

const opt = (...vals: string[]): FieldOption[] =>
  vals.map(v => ({ value: v, label: v }));

// ────────────────────────────────────────────────────────────
//  PROFILE SECTIONS — the left sub-navigation of the detail page
// ────────────────────────────────────────────────────────────

export const PROFILE_SECTIONS: ProfileSection[] = [
  // ── Onboarding steps (same order & labels as the candidate wizard) ────────
  {
    id: "personal",
    label: "Personal",
    icon: "ti-user",
    kind: "grid",
    fields: [
      // ── read-only identity fields (set by system, not editable) ──
      { key: "code",          label: "Employee ID",    type: "readonly" },
      { key: "firstName",     label: "First Name",     type: "readonly" },
      { key: "lastName",      label: "Last Name",      type: "readonly" },
      { key: "dateOfJoining", label: "Date of Joining", type: "readonly" },
      { key: "loginEmail",    label: "Login Email",    type: "readonly" },
      { key: "mobileNumber",  label: "Phone",          type: "readonly" },
      // department/designation are Position-derived only — see the
      // "Reassign Position" action (PromotionTab.tsx), not editable here.
      { key: "department",  label: "Org Unit",    type: "readonly" },
      { key: "designation", label: "Designation", type: "readonly" },
      // ── editable employment fields (options injected at runtime from API) ──
      { key: "ssRole",      label: "Role",        type: "select", required: true, options: [] },
      { key: "branch",            label: "Company Code",     type: "select",   options: [] },
      { key: "reportingManager",  label: "Reporting Manager",  type: "readonly" },
      { key: "reportingApprover", label: "Reporting Approver", type: "readonly" },
      { key: "hr",                label: "Company Code HR",    type: "readonly" },
      // ── personal details ─────────────────────────────────────────
      { key: "dateOfBirth",    label: "Date of Birth",   type: "date",     required: true },
      {
        key: "gender", label: "Gender", type: "radio", required: true,
        options: [{ value: "male", label: "Male" }, { value: "female", label: "Female" }, { value: "other", label: "Other / Prefer not to say" }],
      },
      { key: "maritalStatus",  label: "Marital Status",  type: "select",   options: opt("Single", "Married", "Divorced", "Widowed") },
      { key: "fatherName",     label: "Father's Name",   type: "text",     placeholder: "Father's full name" },
      { key: "bloodGroup",     label: "Blood Group",     type: "select",   options: opt("A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-") },
      // current_address and its sub-fields aren't part of this page's
      // editable set (see EmployeeDetailView.put()'s _PROFILE_FIELD_KEYS on
      // the backend) — self-service (My Profile) or the onboarding wizard is
      // where an employee's current address gets updated, so these render
      // read-only here rather than looking editable but silently no-op-ing.
      { key: "currentAddress",   label: "Address Line 1",   type: "readonly", full: true },
      { key: "currentAddressLine2", label: "Address Line 2", type: "readonly", full: true },
      { key: "currentVillage",   label: "Village / Town / Area", type: "readonly" },
      { key: "currentDistrict",  label: "District",              type: "readonly" },
      { key: "currentState",     label: "State",                 type: "readonly" },
      { key: "currentPinCode",   label: "PIN Code",              type: "readonly" },
      // permanentSameAsCurrent has no real "type" of its own — the detail
      // page's fieldSlot intercepts it and renders a checkbox, and uses its
      // value to hide the four permanent_* fields below in edit mode (same
      // mechanism the manager-picker fields already use).
      { key: "permanentSameAsCurrent", label: "Same as current address", type: "checkbox", full: true },
      { key: "permanentAddress", label: "Address Line 1", type: "text", full: true, placeholder: "House / Flat no., Street" },
      { key: "permanentAddressLine2", label: "Address Line 2", type: "text", full: true, placeholder: "Apartment, floor, landmark" },
      { key: "permanentVillage", label: "Village / Town / Area", type: "text" },
      { key: "permanentDistrict", label: "District",             type: "text" },
      { key: "permanentState",   label: "State",   type: "select", options: opt(...STATES) },
      { key: "permanentPinCode", label: "PIN Code", type: "text", placeholder: "6-digit PIN" },
    ],
  },
  {
    id: "education",
    label: "Education & Experience",
    icon: "ti-school",
    kind: "grid",
    fields: [
      { key: "highestQualification", label: "Highest Qualification",  type: "text",     placeholder: "e.g. B.Tech, MBA" },
      { key: "specialization",       label: "Specialization",         type: "text",     placeholder: "e.g. Computer Science" },
      { key: "institution",          label: "Institution / University", type: "text",   full: true, placeholder: "College or university name" },
      { key: "yearOfPassing",        label: "Year of Passing",         type: "text",    placeholder: "e.g. 2020" },
      { key: "totalExperienceYears", label: "Total Experience (yrs)",  type: "text",    placeholder: "e.g. 3.5" },
      { key: "previousEmployer",     label: "Previous Employer",       type: "text",    placeholder: "Company name (if any)" },
      { key: "previousDesignation",  label: "Previous Designation",    type: "text",    placeholder: "Job title (if any)" },
      { key: "leavingReason",        label: "Reason for Leaving",      type: "textarea", full: true, placeholder: "Optional" },
    ],
  },
  {
    id: "bank",
    label: "Bank Details",
    icon: "ti-building-bank",
    kind: "grid",
    fields: [
      { key: "accountHolderName", label: "Account Holder Name", type: "text",   required: true, placeholder: "As printed on passbook" },
      { key: "accountType",       label: "Account Type",        type: "select", required: true, options: [{ value: "", label: "Select" }, { value: "savings", label: "Savings" }, { value: "current", label: "Current" }] },
      { key: "accountNumber",     label: "Account Number",      type: "text",   required: true, placeholder: "Bank account number" },
      { key: "ifscCode",          label: "IFSC Code",           type: "text",   required: true, placeholder: "e.g. SBIN0001234" },
      { key: "bankName",          label: "Bank Name",           type: "text",   required: true, placeholder: "e.g. State Bank of India" },
      { key: "bankBranch",        label: "Bank Branch",         type: "text",   placeholder: "Branch city / locality" },
    ],
  },
  {
    id: "emergency",
    label: "Emergency Contact",
    icon: "ti-urgent",
    kind: "grid",
    fields: [
      { key: "emergencyName",         label: "Contact Name", type: "text",   required: true, placeholder: "Full name" },
      { key: "emergencyRelationship", label: "Relationship", type: "select", required: true, options: opt("Father", "Mother", "Spouse", "Sibling", "Friend", "Other") },
      { key: "emergencyPhone",        label: "Phone Number", type: "tel",    required: true, placeholder: "+91 XXXXX XXXXX" },
      { key: "emergencyEmail",        label: "Email",        type: "email",  placeholder: "optional@email.com" },
    ],
  },
  {
    id: "epf",
    label: "EPF / Statutory",
    icon: "ti-building-community",
    kind: "grid",
    fields: [
      { key: "uanNumber",       label: "UAN Number",           type: "text", placeholder: "12-digit Universal Account Number" },
      { key: "nameAsPerAadhar", label: "Name as per Aadhar",   type: "text", placeholder: "Exactly as printed on Aadhaar card" },
      { key: "esiNumber",       label: "ESI Number",           type: "text", placeholder: "10-digit ESI Insurance Number (IP Number)" },
    ],
  },
  {
    id: "documents",
    label: "Documents",
    icon: "ti-files",
    kind: "docs",
    documents: [
      { name: "PAN Card",           documentType: "pan_card",           required: true  },
      { name: "Aadhaar Card",       documentType: "aadhaar_card",       required: true  },
      { name: "Degree Certificate", documentType: "degree_certificate", required: false },
      { name: "Experience Letter",  documentType: "experience_letter",  required: false },
      { name: "Passport Photo",     documentType: "passport_photo",     required: true  },
      { name: "Cancelled Cheque",   documentType: "cancelled_cheque",   required: true  },
    ],
  },

];

// ── Settings-driven field config (Settings > Onboarding Fields) ────────────
// PROFILE_SECTIONS' personal/education/bank/emergency FieldDefs use camelCase
// keys (dateOfBirth, fatherName, ...) while OnboardingFieldConfig/EmployeeProfile
// use the backend's snake_case column names — this maps the ones that overlap.
// Fields with no entry here (department, code, uanNumber, ...) aren't covered
// by onboarding-field config and are always shown as-is.
const CAMEL_TO_SNAKE: Record<string, string> = {
  dateOfBirth: "date_of_birth", gender: "gender", maritalStatus: "marital_status",
  fatherName: "father_name", bloodGroup: "blood_group",
  currentAddress: "current_address", currentAddressLine2: "current_address_line2",
  currentVillage: "current_village", currentDistrict: "current_district",
  currentState: "current_state", currentPinCode: "current_pin_code",
  permanentAddress: "permanent_address", permanentAddressLine2: "permanent_address_line2",
  permanentVillage: "permanent_village", permanentDistrict: "permanent_district",
  permanentState: "permanent_state", permanentPinCode: "permanent_pin_code",
  // Not a real OnboardingFieldConfig row of its own — mapped to
  // permanent_address's own visibility so the toggle disappears along with
  // the rest of the permanent-address block when HR hides it.
  permanentSameAsCurrent: "permanent_address",
  highestQualification: "highest_qualification", institution: "institution",
  yearOfPassing: "year_of_passing", specialization: "specialization",
  totalExperienceYears: "total_experience_years", previousEmployer: "previous_employer",
  previousDesignation: "previous_designation", leavingReason: "leaving_reason",
  accountHolderName: "account_holder_name", accountType: "account_type",
  accountNumber: "account_number", ifscCode: "ifsc_code",
  bankName: "bank_name", bankBranch: "bank_branch_name",
  emergencyName: "emergency_name", emergencyRelationship: "emergency_relationship",
  emergencyPhone: "emergency_phone", emergencyEmail: "emergency_email",
};

const SECTION_TO_STEP: Record<string, number> = {
  personal: 0, education: 1, bank: 2, emergency: 3,
};

/**
 * Replaces a "docs" section's static `documents` list with one built from
 * DocumentTypeConfig — same reasoning as applyFieldConfig() below, but for
 * onboarding Step 5. Falls back to the static list if config hasn't loaded
 * yet (empty array) so the page doesn't flash empty while loading.
 */
export function applyDocumentTypeConfig(section: ProfileSection, documentTypeConfig: DocumentTypeConfig[]): ProfileSection {
  if (section.kind !== "docs") return section;
  if (documentTypeConfig.length === 0) return section;
  const documents: DocEntry[] = documentTypeConfig
    .filter(t => t.visible)
    .sort((a, b) => a.order - b.order)
    .map(t => ({ name: t.label, documentType: t.type_key, required: t.required }));
  return { ...section, documents };
}

function fieldTypeFromConfig(type: string): FieldType {
  if (type === "dropdown") return "select";
  if (type === "textarea") return "textarea";
  if (type === "number") return "text";
  if (type === "date") return "date";
  if (type === "checkbox") return "radio";
  // "file" is never actually rendered by FormField — the detail page's
  // fieldSlot intercepts file-type keys before FormField sees them (same
  // mechanism the manager-picker fields already use) — but the type still
  // needs to round-trip correctly rather than falling through to "text".
  if (type === "file") return "file";
  return "text";
}

/**
 * Filters a grid section's built-in fields by the settings-driven visible
 * flag, and appends that step's HR-created custom fields as additional
 * FieldDefs — same config the onboarding wizard and self-service Profile
 * page read, so a field hidden/added in Settings > Onboarding Fields shows
 * up consistently everywhere. Returns the section unchanged if it's not one
 * of the four onboarding-covered sections, or if config hasn't loaded yet
 * (empty {}) — better to show everything than flash-hide fields while
 * loading.
 */
export function applyFieldConfig(section: ProfileSection, fieldConfig: OnboardingFieldConfigByStep): ProfileSection {
  if (section.kind !== "grid") return section;
  const step = SECTION_TO_STEP[section.id];
  if (step === undefined) return section;
  const configs = fieldConfig[String(step)];
  if (!configs || configs.length === 0) return section;

  const visibleFields = section.fields.filter(f => {
    const snakeKey = CAMEL_TO_SNAKE[f.key];
    if (!snakeKey) return true;
    const entry = configs.find(c => c.field_key === snakeKey);
    return entry ? entry.visible : true;
  });

  const customFields: FieldDef[] = configs
    .filter(c => c.is_custom && c.visible)
    .map(c => ({
      key: c.field_key,
      label: c.label,
      type: fieldTypeFromConfig(c.field_type),
      required: c.required,
      full: c.field_type === "textarea",
      options: c.field_type === "dropdown" ? c.options.map(o => ({ value: o, label: o })) : undefined,
    }));

  return { ...section, fields: [...visibleFields, ...customFields] };
}

/** Every custom field_key across all onboarding-covered sections, EXCLUDING
 * file-type fields — used to pull custom_field_values out of the flat
 * `values` state when building the PUT payload. File-type values are never
 * part of that flat state (they upload immediately through their own
 * endpoint, see CustomFieldFileUpload) and have no EmployeeProfile column or
 * custom_field_values entry to send — including them here would only ever
 * send a stray empty string. */
export function customFieldKeys(fieldConfig: OnboardingFieldConfigByStep): string[] {
  return Object.values(fieldConfig).flat().filter(c => c.is_custom && c.field_type !== "file").map(c => c.field_key);
}

// ── top-level tab bar of the detail page ────────────────────
export const PROFILE_TABS = [
  { id: "profile", label: "Profile", icon: "ti-user" },
  { id: "salary", label: "Salary", icon: "ti-currency-rupee" },
  { id: "payroll", label: "Payroll", icon: "ti-receipt" },
  { id: "leave", label: "Leave", icon: "ti-run" },
  { id: "attendance", label: "Attendance", icon: "ti-clock" },
  { id: "approval", label: "Approval Matrix", icon: "ti-sitemap" },
  { id: "promotion", label: "Promotion", icon: "ti-award" },
  { id: "wishes", label: "Send Wishes", icon: "ti-confetti" },
  { id: "audit", label: "Audit Trail", icon: "ti-history" },
] as const;

// ────────────────────────────────────────────────────────────
//  Helpers
// ────────────────────────────────────────────────────────────

export function initials(first: string, last: string): string {
  return `${first[0] ?? ""}${last[0] ?? ""}`.toUpperCase();
}

export function fullName(e: Pick<Employee, "firstName" | "middleName" | "lastName">): string {
  return [e.firstName, e.middleName, e.lastName].filter(Boolean).join(" ");
}

/** Years/months between an ISO date and now → "4 years 5 months" */
export function experienceFrom(iso: string, now = new Date()): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  const start = new Date(y, m - 1, d);
  let months = (now.getFullYear() - start.getFullYear()) * 12 + (now.getMonth() - start.getMonth());
  if (now.getDate() < start.getDate()) months -= 1;
  if (months < 0) months = 0;
  const years = Math.floor(months / 12);
  const rem = months % 12;
  const yp = years > 0 ? `${years} year${years > 1 ? "s" : ""}` : "";
  const mp = rem > 0 ? `${rem} month${rem > 1 ? "s" : ""}` : "";
  return [yp, mp].filter(Boolean).join(" ") || "0 months";
}

export const STATUS_META: Record<EmployeeStatus, { label: string; cls: string; dot: string }> = {
  active: { label: "Active", cls: "bg-[var(--success-c)] text-[var(--success)]", dot: "bg-[var(--success)]" },
  onboarding: { label: "Onboarding", cls: "bg-[var(--warn-c)] text-[var(--warn)]", dot: "bg-[var(--warn)]" },
  inactive: { label: "Inactive", cls: "bg-[var(--bg-high)] text-[var(--on-variant)]", dot: "bg-[var(--outline)]" },
};

// ────────────────────────────────────────────────────────────
//  Colour system — mirrors the dashboard's palette tints so the
//  module uses success/info/warn/gold/purple, not just primary.
// ────────────────────────────────────────────────────────────

export type TintKey = "primary" | "success" | "info" | "warn" | "secondary" | "purple" | "error";

export interface Tint { bg: string; text: string }

/** Soft tints (light bg + coloured icon) — used for badges, stat & icon chips. */
export const TINTS: Record<TintKey, Tint> = {
  primary: { bg: "bg-[rgba(124,58,237,0.10)]", text: "text-[var(--primary)]" },
  success: { bg: "bg-[var(--success-c)]", text: "text-[var(--success)]" },
  info: { bg: "bg-[var(--info-c)]", text: "text-[var(--info)]" },
  warn: { bg: "bg-[var(--warn-c)]", text: "text-[var(--warn)]" },
  secondary: { bg: "bg-[var(--sec-c)]", text: "text-[var(--secondary)]" },
  purple: { bg: "bg-[rgba(167,139,250,0.20)]", text: "text-[var(--purple)]" },
  error: { bg: "bg-[var(--error-c)]", text: "text-[var(--error)]" },
};

/** Department → palette colour (badge + avatar). */
export const DEPARTMENT_TINT: Record<string, TintKey> = {
  Engineering: "primary",
  HR: "success",
  IT: "info",
  Finance: "secondary",
  Sales: "warn",
  Operations: "purple",
  Marketing: "error",
};

/** Solid avatar background per department (readable with white text). */
const DEPARTMENT_AVATAR: Record<string, string> = {
  Engineering: "#7c3aed",
  HR: "#17905a",
  IT: "#2563eb",
  Finance: "#b08423",
  Sales: "#a2620c",
  Operations: "#7c5fb0",
  Marketing: "#c23a2f",
};

export function deptTint(dept: string): Tint {
  return TINTS[DEPARTMENT_TINT[dept] ?? "primary"];
}
export function avatarColor(dept: string): string {
  return DEPARTMENT_AVATAR[dept] ?? "#7c3aed";
}

/** Per-person HSL-tinted avatar (light bg + dark text of the same hue) —
 * the reference Employee Directory table's own confirmed formula:
 * hsl(hue 58% 92%) bg / hsl(hue 52% 34%) text, hue derived per person so
 * each row gets a distinct, stable tint (not tied to department). */
export function personAvatarTint(seed: string): { bg: string; text: string } {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  const hue = hash % 360;
  return { bg: `hsl(${hue} 58% 92%)`, text: `hsl(${hue} 52% 34%)` };
}

/** Each profile section gets a distinct palette colour for its icon chip. */
export const SECTION_TINT: Record<string, TintKey> = {
  personal: "success", education: "secondary", bank: "info", emergency: "error", documents: "warn",
};

// ────────────────────────────────────────────────────────────
//  Directory list API mapping — EmployeeListCreateView.get()'s
//  per-row shape, converted into this module's Employee type.
// ────────────────────────────────────────────────────────────
export interface ApiEmployee {
  id: string; employee_id: string;
  first_name: string; last_name: string; full_name: string;
  email: string; phone: string;
  department: string; designation: string; branch: string;
  role: string; role_display: string;
  date_of_joining: string; is_active: boolean; status: string;
  employment_status?: string;
  confirmation_date?: string | null;
  reporting_manager?: { id: string | null; uuid: string | null; name: string | null } | null;
  last_working_day?: string | null;
  org_unit_name?: string | null;
  org_unit_parent_name?: string | null;
}

export function apiToEmployee(u: ApiEmployee): Employee {
  return {
    id:            u.employee_id || u.id,
    uuid:          u.id,
    code:          u.employee_id || u.id,
    firstName:     u.first_name,
    middleName:    "",
    lastName:      u.last_name,
    email:         u.email,
    phone:         u.phone,
    department:    u.department,
    designation:   u.designation,
    dateOfJoining: u.date_of_joining,
    dateOfBirth:   "",
    location:      u.branch,
    gender:        "male",
    status:        (u.status as EmployeeStatus) || (u.is_active ? "active" : "inactive"),
    employmentStatus: u.employment_status || "probation",
    confirmationDate: u.confirmation_date ?? null,
    reportingManagerName: u.reporting_manager?.name ?? null,
    lastWorkingDay: u.last_working_day ?? null,
    orgUnitName: u.org_unit_name ?? null,
    orgUnitParentName: u.org_unit_parent_name ?? null,
    details: {
      code:          u.employee_id,
      firstName:     u.first_name,
      middleName:    "",
      lastName:      u.last_name,
      gender:        "",
      dateOfBirth:   "",
      dateOfJoining: u.date_of_joining,
      department:    u.department,
      designation:   u.designation,
      branch:        u.branch,
      category:      "General",
      esiLocation:   "Corporate",
      metroTds:      "Metro",
      esiDispensary: "N/A",
      nationality:   "Indian",
      country:       "India",
      loginEmail:    u.email,
      personalEmail: u.email,
      ssRole:        u.role_display || "Employee",
      portalAccess:  "enabled",
      mobileNumber:  u.phone,
    },
    tables: {},
  };
}
