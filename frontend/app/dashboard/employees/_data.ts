// ============================================================
//  Employees feature — types, mock data, section configs, helpers
//  Frontend-only. Swap MOCK_EMPLOYEES for an API call when the
//  backend is ready (see fetchEmployees / fetchEmployee stubs).
// ============================================================

import type { OnboardingFieldConfigByStep } from "@/types/onboardingFieldConfig";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";

export type EmployeeStatus = "active" | "onboarding" | "inactive";
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
  | "select" | "date" | "radio" | "textarea" | "readonly" | "file";

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

const DOC_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

/** Merge an uploaded ApiDocument onto its matching static DocEntry slot. */
export function apiDocumentToEntry(base: DocEntry, doc: ApiDocument): DocEntry {
  const dt = new Date(doc.uploaded_at);
  return {
    ...base,
    status: "pending",
    uploadedOn: `${DOC_MONTHS[dt.getMonth()]} ${dt.getDate()}, ${dt.getFullYear()}`,
    fileUrl: doc.file,
    fileName: doc.file_name,
    fileSize: doc.file_size,
  };
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

const DEPARTMENTS = ["Engineering", "HR", "IT", "Finance", "Sales", "Operations", "Marketing"];
const DESIGNATIONS = [
  "Sr. Manager", "Manager", "Team Lead", "Software Engineer", "Sr. Software Engineer",
  "HR Admin", "System Admin", "Finance Manager", "Sales Executive", "Analyst",
];

export const DEPARTMENT_OPTIONS = DEPARTMENTS;
export const DESIGNATION_OPTIONS = DESIGNATIONS;

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
      // ── editable employment fields (options injected at runtime from API) ──
      { key: "department",  label: "Department",  type: "select", required: true, options: [] },
      { key: "designation", label: "Designation", type: "select", required: true, options: [] },
      { key: "ssRole",      label: "Role",        type: "select", required: true, options: [] },
      { key: "branch",            label: "Branch",           type: "select",   options: [] },
      { key: "reportingManager",  label: "Reporting Manager",  type: "readonly" },
      { key: "reportingApprover", label: "Reporting Approver", type: "readonly" },
      { key: "hr",                label: "Branch HR",          type: "readonly" },
      // ── personal details ─────────────────────────────────────────
      { key: "dateOfBirth",    label: "Date of Birth",   type: "date",     required: true },
      {
        key: "gender", label: "Gender", type: "radio", required: true,
        options: [{ value: "male", label: "Male" }, { value: "female", label: "Female" }, { value: "other", label: "Other / Prefer not to say" }],
      },
      { key: "maritalStatus",  label: "Marital Status",  type: "select",   options: opt("Single", "Married", "Divorced", "Widowed") },
      { key: "fatherName",     label: "Father's Name",   type: "text",     placeholder: "Father's full name" },
      { key: "bloodGroup",     label: "Blood Group",     type: "select",   options: opt("A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-") },
      { key: "currentAddress",   label: "Current Address",   type: "textarea", full: true, placeholder: "House / Flat no., Street, City, State, PIN" },
      { key: "permanentAddress", label: "Permanent Address", type: "textarea", full: true, placeholder: "Leave blank if same as current" },
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
  currentAddress: "current_address", permanentAddress: "permanent_address",
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
] as const;

// ────────────────────────────────────────────────────────────
//  Helpers
// ────────────────────────────────────────────────────────────

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function initials(first: string, last: string): string {
  return `${first[0] ?? ""}${last[0] ?? ""}`.toUpperCase();
}

export function fullName(e: Pick<Employee, "firstName" | "middleName" | "lastName">): string {
  return [e.firstName, e.middleName, e.lastName].filter(Boolean).join(" ");
}

/** "2022-01-15" → "Jan 15, 2022" */
export function formatDate(iso: string): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

/** "2022-01-15" → "15-01-2022" (for date inputs displayed dd-mm-yyyy) */
export function toDisplayDmy(iso: string): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return [d, m, y].join("-");
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
  primary: { bg: "bg-[rgba(30,78,140,0.10)]", text: "text-[var(--primary)]" },
  success: { bg: "bg-[var(--success-c)]", text: "text-[var(--success)]" },
  info: { bg: "bg-[var(--info-c)]", text: "text-[var(--info)]" },
  warn: { bg: "bg-[var(--warn-c)]", text: "text-[var(--warn)]" },
  secondary: { bg: "bg-[var(--sec-c)]", text: "text-[var(--secondary)]" },
  purple: { bg: "bg-[rgba(173,149,207,0.20)]", text: "text-[var(--purple)]" },
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
  Engineering: "#1e4e8c",
  HR: "#1b8a6b",
  IT: "#0e7c86",
  Finance: "#b08423",
  Sales: "#b5651d",
  Operations: "#7c5fb0",
  Marketing: "#c0392b",
};

export function deptTint(dept: string): Tint {
  return TINTS[DEPARTMENT_TINT[dept] ?? "primary"];
}
export function avatarColor(dept: string): string {
  return DEPARTMENT_AVATAR[dept] ?? "#1e4e8c";
}

/** Each profile section gets a distinct palette colour for its icon chip. */
export const SECTION_TINT: Record<string, TintKey> = {
  personal: "success", education: "secondary", bank: "info", emergency: "error", documents: "warn",
};

// ────────────────────────────────────────────────────────────
//  MOCK DATA  (replace with API — see stubs at bottom)
// ────────────────────────────────────────────────────────────

function emp(
  base: Omit<Employee, "details" | "tables">,
  details: DetailValues = {},
  tables: Record<string, TableRow[]> = {},
): Employee {
  return {
    ...base,
    details: {
      // sensible defaults so the form is never blank
      code: base.code,
      firstName: base.firstName,
      middleName: base.middleName,
      lastName: base.lastName,
      gender: base.gender,
      dateOfBirth: base.dateOfBirth,
      dateOfJoining: base.dateOfJoining,
      department: base.department,
      designation: base.designation,
      category: "General",
      esiLocation: "Corporate",
      metroTds: "Metro",
      esiDispensary: "N/A",
      employeeType: "Permanent",
      employmentStatus: "Active",
      nationality: "Indian",
      country: "India",
      loginEmail: base.email,
      personalEmail: base.email,
      ssRole: "Employee",
      portalAccess: "enabled",
      ...details,
    },
    tables,
  };
}

export const MOCK_EMPLOYEES: Employee[] = [
  emp(
    {
      id: "RSS00001D", code: "RSS00001D", firstName: "Arjun", middleName: "", lastName: "Mehta",
      email: "manager@royal.com", phone: "+91 98765 10011", department: "Engineering",
      designation: "Sr. Manager", dateOfJoining: "2022-01-15", dateOfBirth: "1985-04-15",
      location: "Bengaluru, KA", gender: "male", status: "active"
    },
    {
      ssRole: "Manager", grade: "M3", reportingTo: "Sunil Varghese", workLocation: "Head Office",
      maritalStatus: "Married", bloodGroup: "O+", city: "Bengaluru", state: "Karnataka", pincode: "560001",
      ecName: "Neha Mehta", ecRelationship: "Spouse", ecPrimaryPhone: "+91 98765 10012"
    },
    {
      family: [
        { _id: "f1", name: "Neha Mehta", relationship: "Spouse", dob: "1987-09-12", occupation: "Teacher", dependent: "no" },
        { _id: "f2", name: "Aarav Mehta", relationship: "Son", dob: "2015-03-04", occupation: "Student", dependent: "yes" },
      ],
      academic: [
        { _id: "a1", qualification: "B.Tech", institution: "NIT Trichy", specialization: "Computer Science", year: "2007", score: "8.6 CGPA" },
        { _id: "a2", qualification: "MBA", institution: "IIM Bangalore", specialization: "Operations", year: "2011", score: "7.9 CGPA" },
      ],
      language: [
        { _id: "l1", language: "English", read: "yes", write: "yes", speak: "yes" },
        { _id: "l2", language: "Hindi", read: "yes", write: "yes", speak: "yes" },
        { _id: "l3", language: "Kannada", read: "no", write: "no", speak: "yes" },
      ],
    },
  ),
  emp(
    {
      id: "RSS00002D", code: "RSS00002D", firstName: "Kavitha", middleName: "", lastName: "Rajan",
      email: "hr@royal.com", phone: "+91 98765 20022", department: "HR",
      designation: "HR Admin", dateOfJoining: "2021-03-01", dateOfBirth: "1990-07-22",
      location: "Chennai, TN", gender: "female", status: "active"
    },
    {
      ssRole: "HR Admin", grade: "M2", reportingTo: "Sunil Varghese", workLocation: "Chennai Branch",
      maritalStatus: "Single", bloodGroup: "B+", city: "Chennai", state: "Tamil Nadu", pincode: "600001"
    },
  ),
  emp(
    {
      id: "RSS00003D", code: "RSS00003D", firstName: "Ravi", middleName: "", lastName: "Shankar",
      email: "admin@royal.com", phone: "+91 98765 30033", department: "IT",
      designation: "System Admin", dateOfJoining: "2020-06-10", dateOfBirth: "1988-11-05",
      location: "Hyderabad, TS", gender: "male", status: "active"
    },
    {
      ssRole: "System Admin", grade: "M3", reportingTo: "Sunil Varghese", workLocation: "Head Office",
      maritalStatus: "Married", bloodGroup: "A+", city: "Hyderabad", state: "Telangana", pincode: "500001"
    },
  ),
  emp(
    {
      id: "RSS00004D", code: "RSS00004D", firstName: "Priya", middleName: "", lastName: "Sharma",
      email: "employee@royal.com", phone: "+91 98765 40044", department: "Engineering",
      designation: "Software Engineer", dateOfJoining: "2025-06-20", dateOfBirth: "1998-02-18",
      location: "Bengaluru, KA", gender: "female", status: "active"
    },
    {
      ssRole: "Employee", grade: "E2", reportingTo: "Arjun Mehta", workLocation: "Head Office",
      maritalStatus: "Single", bloodGroup: "O-", city: "Bengaluru", state: "Karnataka", pincode: "560037"
    },
  ),
  emp(
    {
      id: "RSS00005D", code: "RSS00005D", firstName: "Meena", middleName: "", lastName: "Iyer",
      email: "meena@royal.com", phone: "+91 98765 50055", department: "Finance",
      designation: "Finance Manager", dateOfJoining: "2021-08-05", dateOfBirth: "1986-12-30",
      location: "Mumbai, MH", gender: "female", status: "active"
    },
    {
      ssRole: "Manager", grade: "M3", reportingTo: "Sunil Varghese", workLocation: "Mumbai Branch",
      maritalStatus: "Married", bloodGroup: "AB+", city: "Mumbai", state: "Maharashtra", pincode: "400001",
      metroTds: "Metro", profTaxLocation: "Maharashtra"
    },
  ),
  emp(
    {
      id: "RSS00006D", code: "RSS00006D", firstName: "Suresh", middleName: "", lastName: "Kumar",
      email: "suresh@royal.com", phone: "+91 98765 60066", department: "Sales",
      designation: "Sales Executive", dateOfJoining: "2025-06-18", dateOfBirth: "1995-05-09",
      location: "Pune, MH", gender: "male", status: "onboarding"
    },
    {
      ssRole: "Employee", grade: "E1", reportingTo: "Meena Iyer", workLocation: "Pune Branch",
      employmentStatus: "Active", maritalStatus: "Single", bloodGroup: "B-", city: "Pune", state: "Maharashtra", pincode: "411001"
    },
  ),
];

// ── data-access stubs (swap to real API later) ──────────────
export function getEmployees(): Employee[] {
  return MOCK_EMPLOYEES;
}
export function getEmployee(id: string): Employee | undefined {
  return MOCK_EMPLOYEES.find(e => e.id === id || e.code === id);
}

export function addEmployee(emp: Employee): void {
  MOCK_EMPLOYEES.unshift(emp);
}

export function updateEmployee(
  id: string,
  details: DetailValues,
  tables: Record<string, TableRow[]>,
): void {
  const emp = MOCK_EMPLOYEES.find(e => e.id === id || e.code === id);
  if (!emp) return;
  // persist detail values
  Object.assign(emp.details, details);
  // sync top-level Employee fields so ProfileHeader reflects changes
  if (details.firstName)                emp.firstName    = details.firstName;
  if (details.middleName !== undefined) emp.middleName   = details.middleName;
  if (details.lastName)                 emp.lastName     = details.lastName;
  if (details.designation)              emp.designation  = details.designation;
  if (details.department)               emp.department   = details.department;
  if (details.dateOfBirth)              emp.dateOfBirth  = details.dateOfBirth;
  if (details.dateOfJoining)            emp.dateOfJoining = details.dateOfJoining;
  if (details.mobileNumber)             emp.phone        = details.mobileNumber;
  // persist table rows
  Object.assign(emp.tables, tables);
}
