// ─── Document Type Configuration — Settings + Wizard ──────────────────────────
// Per-company configuration for onboarding Step 5 (Documents) — sibling of
// onboardingFieldConfig.ts for steps 0-3. Every document upload's "type"
// (PAN Card, Aadhaar Card, ...) is one of these rows rather than a hardcoded
// enum; is_custom=false rows are the 7 built-ins, is_custom=true are ones HR
// added at runtime.

export interface DocumentTypeConfig {
  type_key: string;
  label: string;
  order: number;
  visible: boolean;
  required: boolean;
  allow_multiple: boolean;
  is_custom: boolean;
  is_locked: boolean;
  updated_at: string;
}

export interface CreateDocumentTypePayload {
  label: string;
  required?: boolean;
  allow_multiple?: boolean;
}

export interface UpdateDocumentTypePayload {
  label?: string;
  order?: number;
  visible?: boolean;
  required?: boolean;
  allow_multiple?: boolean;
}
