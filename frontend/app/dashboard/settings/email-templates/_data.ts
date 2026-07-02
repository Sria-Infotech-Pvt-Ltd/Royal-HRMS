// ─── API endpoints ────────────────────────────────────────────────────────────
export const EMAIL_TEMPLATES_BASE           = "/settings/email-templates/";
export const emailTemplateDetail            = (id: number) => `/settings/email-templates/${id}/`;
export const emailTemplatePreview           = (id: number) => `/settings/email-templates/${id}/preview/`;
export const emailTemplateAttachmentDetail  = (templateId: number, attachmentId: number) =>
  `/settings/email-templates/${templateId}/attachments/${attachmentId}/`;
export const EMAIL_TEMPLATE_CATEGORIES      = "/settings/email-template-categories/";

// ─── API types ────────────────────────────────────────────────────────────────

export type TemplateType = "document" | "notification" | "reminder" | "wish";

export interface ApiAttachment {
  id:          number;
  filename:    string;
  mime_type:   string;
  size:        number;
  url:         string;
  uploaded_at: string;
}

export interface ApiTemplateCategory {
  id:    number;
  name:  string;
  code?: string;   // e.g. "document" | "notification" | "reminder" | "wish"
  slug?: string;
}

export interface ApiEmailTemplate {
  id:                    number;
  name:                  string;           // slug, e.g. "payslip"
  display_name:          string;           // e.g. "Pay Slip"
  description:           string;
  template_type:         TemplateType;
  template_type_display: string;           // e.g. "Document"
  subject:               string;
  body:                  string;
  is_active:             boolean;
  is_builtin:            boolean;
  available_variables:   string[] | string; // API may return array or JSON string
  attachments:           ApiAttachment[];
  updated_at:            string;
}

// Response envelope: data is a record keyed by template_type
export type ApiEmailTemplatesResponse = Record<TemplateType, ApiEmailTemplate[]>;

// Flatten the grouped response into a single array
export function flattenTemplates(data: ApiEmailTemplatesResponse): ApiEmailTemplate[] {
  return (Object.values(data) as ApiEmailTemplate[][]).flat();
}

// Backend stores available_variables as a JSON-stringified string, e.g. "[\"A\",\"B\"]"
// Always call this when reading the field from any API response.
export function parseAvailableVars(val: unknown): string[] {
  if (Array.isArray(val)) return val as string[];
  if (typeof val === "string" && val.trim().startsWith("[")) {
    try { return JSON.parse(val) as string[]; } catch { /* fall through */ }
  }
  return [];
}

// ─── Form ─────────────────────────────────────────────────────────────────────

export interface TemplateForm {
  name:                string;    // slug: lowercase, digits, underscores (add mode only)
  display_name:        string;    // human-readable label (add mode only)
  template_type:       string;    // category code e.g. "document" | "notification" | "reminder" | "wish"
  subject:             string;
  body:                string;
  attachments:         File[];
  available_variables: string[];
}

export const EMPTY_TEMPLATE_FORM: TemplateForm = { name: "", display_name: "", template_type: "", subject: "", body: "", attachments: [], available_variables: [] };

// Convert a display name to a valid slug automatically
export function toSlug(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9\s_]/g, "")
    .trim()
    .replace(/\s+/g, "_")
    .replace(/^[^a-z]+/, "");   // must start with a letter
}

// Accepted MIME types
export const ATTACHMENT_ACCEPT = [
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
].join(",");

export const ATTACHMENT_ACCEPT_ATTR = ".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.webp,.svg";

export type FileKind = "pdf" | "word" | "excel" | "image" | "other";

export function fileKind(file: File): FileKind {
  const n = file.name.toLowerCase();
  if (n.endsWith(".pdf"))  return "pdf";
  if (n.endsWith(".doc") || n.endsWith(".docx")) return "word";
  if (n.endsWith(".xls") || n.endsWith(".xlsx")) return "excel";
  if (file.type.startsWith("image/")) return "image";
  return "other";
}

export const FILE_KIND_META: Record<FileKind, { icon: string; color: string; bg: string }> = {
  pdf:   { icon: "ti-file-type-pdf",  color: "#e53e3e", bg: "rgba(229,62,62,0.08)"   },
  word:  { icon: "ti-file-type-docx", color: "#2b6cb0", bg: "rgba(43,108,176,0.08)"  },
  excel: { icon: "ti-file-type-xls",  color: "#276749", bg: "rgba(39,103,73,0.08)"   },
  image: { icon: "ti-photo",          color: "#6b46c1", bg: "rgba(107,70,193,0.08)"  },
  other: { icon: "ti-file",           color: "var(--outline)", bg: "var(--bg-low)"   },
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024)        return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export type TemplateFormErrors = Partial<Record<keyof TemplateForm, string>>;

const SLUG_RE = /^[a-z][a-z0-9_]*$/;

export function validateTemplateForm(form: TemplateForm, isAdd: boolean): TemplateFormErrors {
  const e: TemplateFormErrors = {};
  if (isAdd) {
    if (!form.display_name.trim())  e.display_name  = "Display name is required";
    if (!form.name.trim())          e.name          = "Slug is required";
    else if (!SLUG_RE.test(form.name)) e.name       = "Slug must start with a letter and contain only lowercase letters, digits, and underscores";
    if (!form.template_type.trim()) e.template_type = "Category is required";
  }
  if (!form.subject.trim()) e.subject = "Subject is required";
  if (!form.body.trim())    e.body    = "Body is required";
  return e;
}

// ─── Category value extractor (shared between page and modal) ─────────────────

export function catValue(cat: ApiTemplateCategory): string {
  return cat.code ?? cat.slug ?? cat.name.toLowerCase().replace(/\s+templates?$/i, "").trim();
}

// ─── Type metadata ────────────────────────────────────────────────────────────

export const TYPE_META: Record<TemplateType, { label: string; color: string; icon: string }> = {
  document:     { label: "Document",     color: "var(--primary)", icon: "ti-file-text"        },
  notification: { label: "Notification", color: "var(--info)",    icon: "ti-bell-ringing"     },
  reminder:     { label: "Reminder",     color: "var(--warn)",    icon: "ti-bell"             },
  wish:         { label: "Wish",         color: "var(--success)", icon: "ti-confetti"         },
};
