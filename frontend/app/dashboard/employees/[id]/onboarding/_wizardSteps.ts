// Pure wizard-step data for the HR-side onboarding wizard — no component
// state, safe to import from anywhere. Mirrors app/onboarding/_wizardSteps.ts
// (the self-service wizard's own copy) — see that file's comments for the
// full reasoning behind the sentinel step numbers.

import type { ProfileForm } from "@/app/onboarding/_types";

export const EMPTY: ProfileForm = {
  date_of_birth: "", gender: "", marital_status: "", father_name: "", blood_group: "",
  current_address: "", current_address_line2: "",
  current_village: "", current_district: "", current_state: "", current_pin_code: "",
  permanent_address: "", permanent_address_line2: "",
  permanent_village: "", permanent_district: "", permanent_state: "", permanent_pin_code: "",
  permanent_same_as_current: "false",
  highest_qualification: "", institution: "", year_of_passing: "", specialization: "",
  total_experience_years: "", previous_employer: "", previous_designation: "", leaving_reason: "",
  account_number: "", ifsc_code: "", bank_name: "", bank_branch_name: "",
  account_holder_name: "", account_type: "",
  emergency_name: "", emergency_relationship: "", emergency_phone: "", emergency_email: "",
  pan_number: "",
};

export const PAN_RE = /^[A-Za-z]{5}[0-9]{4}[A-Za-z]$/;

export type WizardStep = { step: number; label: string; shortLabel: string; icon: string; kind: "fields" | "documents" | "education" | "experience" | "family-nomination" | "assets" };

export const BUILTIN_STEPS: WizardStep[] = [
  { step: 0,  label: "Personal",          shortLabel: "Personal",   icon: "ti-user",          kind: "fields" },
  { step: -2, label: "Education",         shortLabel: "Education",  icon: "ti-school",        kind: "education" },
  { step: -3, label: "Experience",        shortLabel: "Experience", icon: "ti-briefcase",     kind: "experience" },
  { step: 2,  label: "Bank Details",      shortLabel: "Bank",       icon: "ti-building-bank", kind: "fields" },
  { step: 3,  label: "Emergency Contact", shortLabel: "Emergency",  icon: "ti-urgent",        kind: "fields" },
  { step: -4, label: "Family & Nomination", shortLabel: "Family",   icon: "ti-users",         kind: "family-nomination" },
  { step: -5, label: "Assets",            shortLabel: "Assets",     icon: "ti-device-laptop", kind: "assets" },
];
export const DOCUMENTS_STEP: WizardStep = { step: 4, label: "Documents", shortLabel: "Documents", icon: "ti-files", kind: "documents" };
