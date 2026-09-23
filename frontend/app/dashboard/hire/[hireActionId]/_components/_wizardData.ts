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

export function emptyEmergencyContact(id: string, isPrimary: boolean): EmergencyContactEntry {
  return { id, name: "", relationship: "", phone: "", alternate_phone: "", email: "", address: "", is_primary: isPrimary };
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
