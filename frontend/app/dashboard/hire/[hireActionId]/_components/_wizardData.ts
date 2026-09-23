// Pure types/constants/helpers for the Hire wizard — no component state,
// safe to import from anywhere.

import type { ProfileForm } from "@/app/onboarding/_types";
import type { EmergencyContactEntry } from "./EmergencyContactsList";
import type { HireStepDef } from "./HireWizardSidebar";

export const EMPTY_FORM: ProfileForm = {
  date_of_birth: "", gender: "", marital_status: "", father_name: "", blood_group: "",
  current_address: "", current_address_line2: "", current_village: "", current_district: "",
  current_state: "", current_pin_code: "", permanent_address: "", permanent_address_line2: "",
  permanent_village: "", permanent_district: "", permanent_state: "", permanent_pin_code: "",
  permanent_same_as_current: "false", highest_qualification: "", institution: "", year_of_passing: "",
  specialization: "", total_experience_years: "", previous_employer: "", previous_designation: "",
  leaving_reason: "", account_number: "", ifsc_code: "", bank_name: "", bank_branch_name: "",
  account_holder_name: "", account_type: "", emergency_name: "", emergency_relationship: "",
  emergency_phone: "", emergency_email: "", pan_number: "",
};

export interface IdentityExtras {
  mother_name: string;
  languages_known: string;
  alternate_mobile: string;
  specially_abled: string;
  international_worker: string;
  category: string;
}

export const EMPTY_IDENTITY_EXTRAS: IdentityExtras = {
  mother_name: "", languages_known: "", alternate_mobile: "",
  specially_abled: "no", international_worker: "no", category: "prefer_not_to_say",
};

// Excluded from the shared DynamicStepFields render for step 1 — the
// repeatable EmergencyContactsList below replaces the single fixed set of
// emergency_* fields that component would otherwise render.
export const EMERGENCY_BUILTIN_KEYS = new Set(["emergency_name", "emergency_relationship", "emergency_phone", "emergency_email"]);

// Excluded from the shared DynamicStepFields render for step 1 — the
// AddressFields component below replaces the generic reused current/
// permanent address rendering with the exact reference layout (Landmark/
// City/District row, explicit "+Suggest" buttons, Yes/No toggle).
export const ADDRESS_BUILTIN_KEYS = new Set([
  "current_address", "current_address_line2", "current_village", "current_district", "current_state", "current_pin_code",
  "permanent_address", "permanent_address_line2", "permanent_village", "permanent_district", "permanent_state", "permanent_pin_code",
  "permanent_same_as_current",
]);

// Excluded from the shared DynamicStepFields render on step 1 (Personal
// identity) — every one of these already has its own hardcoded field
// earlier in this same step (Date of birth/Gender/Marital status/Blood
// group/Father's name — the "Basic details" grid) or on a LATER step
// (Aadhaar/Passport — Statutory & accounts, step 4). Without this
// exclusion, the org's onboarding-step-0 field config (meant for the
// self-service onboarding wizard, which asks these in one combined step)
// gets merged in wholesale and every one of these questions is asked
// twice — worse for Aadhaar/Passport, since that second copy writes into
// `form` while the real Statutory & accounts step reads from its own
// separate `statutoryDraft` state, so anything typed into the step-1 copy
// is silently never used.
export const IDENTITY_STATUTORY_BUILTIN_KEYS = new Set([
  "date_of_birth", "gender", "marital_status", "blood_group", "father_name",
  "aadhaar_number", "passport_number", "passport_expiry",
]);

export function emptyEmergencyContact(id: string, isPrimary: boolean): EmergencyContactEntry {
  return { id, name: "", relationship: "", phone: "", alternate_phone: "", email: "", address: "", is_primary: isPrimary };
}

// Personal Identity step validation constants/helpers.
export const HAS_DIGIT_RE = /\d/;
export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// Statutory & accounts step validation — standard PAN (5 letters, 4 digits,
// 1 letter) and IFSC (4 letters, a literal 0, 6 alphanumerics) formats.
export const PAN_RE = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
export const IFSC_RE = /^[A-Z]{4}0[A-Z0-9]{6}$/;
export const MS_PER_YEAR = 1000 * 60 * 60 * 24 * 365.25;
export const MIN_HIRE_AGE_YEARS = 18;
export const MAX_PLAUSIBLE_AGE_YEARS = 100;
// PhoneInput stores "+<dial> <national>" — count digits everywhere (dial
// code included) rather than trying to re-split it, so this only needs one
// simple floor: 8 total digits comfortably covers every real dial-code +
// national-number combination in PhoneInput's own country list (the
// shortest, dial code "1", pairs with a 10-digit US/Canada number) while
// still catching an obviously truncated/garbage entry.
export const MIN_PHONE_DIGITS = 8;
export function phoneDigitCount(value: string): number {
  return value.replace(/\D/g, "").length;
}

export interface HireActionData {
  id: string; reason: string; reason_display: string; effective_from: string; position: string;
  position_title: string; org_unit_name: string; grade: string;
  employment_type: string; reserved_employee_id: string; status: string;
  draft_data: Record<string, unknown>;
  photo_url: string | null;
}

export const STEPS: HireStepDef[] = [
  { label: "Personal identity", sub: "Name, photo, DOB, contact", required: 7 },
  { label: "Employment", sub: "Role, reporting, work setup", required: 5 },
  { label: "Basic pay", sub: "Wage types and pay scale" },
  { label: "Statutory & accounts", sub: "PAN, PF, ESI, bank", required: 5, tag: { label: "Sensitive", tone: "sensitive" } },
  { label: "Family & nomination", sub: "Dependants and nominees", group: "Records & compliance", tag: { label: "EPFO", tone: "info" } },
  { label: "Education & experience", sub: "Qualifications, past employers" },
  { label: "Documents", sub: "Joining paperwork" },
  { label: "Assets", sub: "Laptop, phone, access card", tag: { label: "New", tone: "new" } },
  { label: "Review", sub: "Confirm and hire" },
];
