// ─── Onboarding Field Configuration — Settings + Wizard ───────────────────────
// Per-company configuration for the self-onboarding wizard's steps 0-3
// (Personal, Education, Bank, Emergency). Step 4/Documents is a separate
// file-upload flow and isn't covered by this config.

export type OnboardingFieldType = "text" | "textarea" | "number" | "date" | "dropdown" | "checkbox" | "file";

export interface OnboardingFieldConfig {
  field_key: string;
  label: string;
  field_type: OnboardingFieldType;
  options: string[]; // dropdown choices only
  allow_multiple: boolean; // file fields only — single slot vs a growing list
  step: number; // 0-3
  order: number;
  visible: boolean;
  required: boolean;
  is_custom: boolean;
  is_locked: boolean;
  updated_at: string;
}

export interface OnboardingFieldConfigByStep {
  [step: string]: OnboardingFieldConfig[];
}

export interface CreateOnboardingFieldPayload {
  label: string;
  field_type: OnboardingFieldType;
  options?: string[];
  allow_multiple?: boolean;
  step: number;
  required?: boolean;
}

// A single uploaded value for a file-type custom field — returned by the
// /onboarding/custom-file-fields/ and /employees/<id>/custom-file-fields/
// endpoints, never stored in EmployeeProfile.custom_field_values (see the
// backend's CustomFieldFileValue model docstring).
export interface CustomFieldFileValue {
  id: number;
  field_key: string;
  file_url: string | null;
  file_name: string;
  file_size: number;
  uploaded_at: string;
}

export interface UpdateOnboardingFieldPayload {
  label?: string;
  options?: string[];
  order?: number;
  visible?: boolean;
  required?: boolean;
}

// ─── Education/Experience field configuration ─────────────────────────────────
// Show/require toggles for the optional fields on each Education/Experience
// *entry* (a genuinely repeatable list, not a single flat step) — a
// narrower sibling of OnboardingFieldConfig above: HR can show/hide and
// require any of these existing fields, but can't add a brand-new custom
// one (see backend EducationExperienceFieldConfig's own docstring for why).
export interface EducationExperienceFieldConfig {
  id: string;
  list_type: "education" | "experience";
  field_key: string;
  label: string;
  visible: boolean;
  required: boolean;
  order: number;
}

export interface EducationExperienceFieldConfigResponse {
  education: EducationExperienceFieldConfig[];
  experience: EducationExperienceFieldConfig[];
}

export const ONBOARDING_STEP_LABELS: Record<number, string> = {
  0: "Personal Information",
  1: "Education & Experience",
  2: "Bank Details",
  3: "Emergency Contact",
};

// ─── Onboarding Sections — HR-created custom wizard tabs ──────────────────────
// Sit alongside the 4 built-in steps above (and before the separate
// Documents step) — a section's own `step` number (always 5+) is what an
// OnboardingFieldConfig row's `step` points to when it belongs to one.

export interface OnboardingSection {
  id: string;
  step: number; // 5+, server-assigned, never reused
  label: string;
  icon: string; // Tabler icon class, e.g. "ti-folder"
  order: number;
  is_active: boolean;
  updated_at: string;
}

export interface CreateOnboardingSectionPayload {
  label: string;
  icon?: string;
}

export interface UpdateOnboardingSectionPayload {
  label?: string;
  icon?: string;
  order?: number;
  is_active?: boolean;
}
