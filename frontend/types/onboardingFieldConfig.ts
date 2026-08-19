// ─── Onboarding Field Configuration — Settings + Wizard ───────────────────────
// Per-company configuration for the self-onboarding wizard's steps 0-3
// (Personal, Education, Bank, Emergency). Step 4/Documents is a separate
// file-upload flow and isn't covered by this config.

export type OnboardingFieldType = "text" | "textarea" | "number" | "date" | "dropdown" | "checkbox";

export interface OnboardingFieldConfig {
  field_key: string;
  label: string;
  field_type: OnboardingFieldType;
  options: string[]; // dropdown choices only
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
  step: number;
  required?: boolean;
}

export interface UpdateOnboardingFieldPayload {
  label?: string;
  options?: string[];
  order?: number;
  visible?: boolean;
  required?: boolean;
}

export const ONBOARDING_STEP_LABELS: Record<number, string> = {
  0: "Personal Information",
  1: "Education & Experience",
  2: "Bank Details",
  3: "Emergency Contact",
};
