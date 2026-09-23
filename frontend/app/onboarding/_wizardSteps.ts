// Pure wizard-step data for the self-service onboarding page — no component
// state, safe to import from anywhere.

import type { ProfileForm } from "./_types";

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

// Each entry carries its own real backend `step` number and a `kind` saying
// which component renders it — `tab` (component state) is only ever an
// index into the merged `steps` array below, never assumed to equal the
// backend step number itself. That split is what lets HR-created custom
// sections (step 5+, see OnboardingSection) slot in between Emergency
// Contact and Documents without shifting Documents'/Face ID's own identity.
export type WizardStep = { step: number; label: string; shortLabel: string; icon: string; kind: "fields" | "documents" | "face" | "education" | "experience" | "family-nomination" | "assets" };

// Education and Experience are their own bespoke steps now (a fixed
// checklist and a real add/remove list respectively — neither fits the
// generic OnboardingFieldConfig "one config = one flat value" model any
// more than Documents/Face ID do). `step: -2`/`-3` are sentinels, same
// convention as Face ID's `step: -1` below — neither ever round-trips
// through /onboarding/step/<n>/, so no real step number is needed, and
// this sidesteps any future collision with HR-created custom sections
// (server-assigned, always >= 5, growing forever). Family & Nomination
// (-4) and Assets (-5) follow the exact same sentinel convention.
export const BUILTIN_STEPS: WizardStep[] = [
  { step: 0,  label: "Personal",          shortLabel: "Personal",   icon: "ti-user",          kind: "fields" },
  { step: -2, label: "Education",         shortLabel: "Education",  icon: "ti-school",        kind: "education" },
  { step: -3, label: "Experience",        shortLabel: "Experience", icon: "ti-briefcase",     kind: "experience" },
  { step: 2,  label: "Bank Details",      shortLabel: "Bank",       icon: "ti-building-bank", kind: "fields" },
  { step: 3,  label: "Emergency Contact", shortLabel: "Emergency",  icon: "ti-urgent",         kind: "fields" },
  { step: -4, label: "Family & Nomination", shortLabel: "Family",   icon: "ti-users",         kind: "family-nomination" },
  { step: -5, label: "Assets",            shortLabel: "Assets",     icon: "ti-device-laptop", kind: "assets" },
];

export const DOCUMENTS_STEP: WizardStep = { step: 4, label: "Documents", shortLabel: "Documents", icon: "ti-files", kind: "documents" };

// Appended only when the admin's org-wide Face ID Verification toggle
// (Attendance Settings) is mandatory — see the faceMandatory fetch below. When
// off, the step doesn't exist at all: the employee never sees it, and
// "Submit for Approval" appears directly after Documents. When on, it's
// required — the submit button below stays disabled until a face
// registration has actually been submitted (see canSubmit). Always the LAST
// step. `step: -1` is a sentinel — Face ID never round-trips through
// /onboarding/step/<n>/, so no real step number is needed for it.
export const FACE_STEP: WizardStep = { step: -1, label: "Face ID", shortLabel: "Face ID", icon: "ti-face-id", kind: "face" };
