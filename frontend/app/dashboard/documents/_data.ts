import { formatDate } from "@/lib/formatDate";

// ─── Endpoints ────────────────────────────────────────────────────────────────
export const DOCUMENTS_BASE   = "/documents/";
export const DOCUMENTS_STATS  = "/documents/stats/";
export const documentDetail   = (id: number) => `/documents/${id}/`;

// ─── Types ────────────────────────────────────────────────────────────────────

export type DocCategory = "policy" | "form" | "template" | "other";

export type ApiFileType =
  | "PDF" | "DOC" | "DOCX" | "XLS" | "XLSX"
  | "PPT" | "PPTX" | "JPG" | "PNG" | "TXT" | "CSV";

export interface ApiDocument {
  id:                number;
  title:             string;
  description:       string;
  category:          DocCategory;
  category_display:  string;
  // Only meaningful for category === "policy" — blank/null for other
  // categories (forms/templates/other never carry a version number).
  version:           string;
  effective_date:    string | null;  // ISO date (YYYY-MM-DD), or null
  file:              string;
  file_url:          string;
  file_name:         string;
  file_type:         ApiFileType;
  file_size:         number;
  file_size_display: string;
  branch:            number | null;
  branch_name:       string | null;
  uploaded_by_name:  string;
  uploaded_at:       string;  // ISO 8601
  updated_at:        string;
  is_active:         boolean;
}

export interface ApiStatsResponse {
  total:       number;
  by_category: Record<DocCategory, number>;
}

// ─── Form ─────────────────────────────────────────────────────────────────────

export interface DocUploadForm {
  title:          string;
  description:    string;
  category:       DocCategory | "";
  // Only shown/settable in the UI when category === "policy" — optional for
  // every other category, so leaving them blank never blocks an upload.
  version:        string;
  effective_date: string;  // ISO date (YYYY-MM-DD) or "" if unset
  file:           File | null;
}

export const EMPTY_UPLOAD_FORM: DocUploadForm = {
  title: "", description: "", category: "", version: "", effective_date: "", file: null,
};

export type DocUploadErrors = Partial<Record<keyof DocUploadForm, string>>;

export function validateUploadForm(form: DocUploadForm): DocUploadErrors {
  const e: DocUploadErrors = {};
  if (!form.title.trim()) e.title    = "Document name is required";
  if (!form.category)     e.category = "Category is required";
  if (!form.file)         e.file     = "Please select a file";
  return e;
}

// ─── File-type metadata ───────────────────────────────────────────────────────

type IconClass = "pdf" | "doc" | "xls" | "ppt" | "img" | "txt";

interface FileTypeMeta {
  icon:      string;
  iconClass: IconClass;
  label:     string;
}

export const FILE_TYPE_META: Record<string, FileTypeMeta> = {
  PDF:  { icon: "ti-file-type-pdf",  iconClass: "pdf", label: "PDF"  },
  DOC:  { icon: "ti-file-type-docx", iconClass: "doc", label: "DOC"  },
  DOCX: { icon: "ti-file-type-docx", iconClass: "doc", label: "DOCX" },
  XLS:  { icon: "ti-file-type-xls",  iconClass: "xls", label: "XLS"  },
  XLSX: { icon: "ti-file-type-xls",  iconClass: "xls", label: "XLSX" },
  CSV:  { icon: "ti-file-spreadsheet", iconClass: "xls", label: "CSV" },
  PPT:  { icon: "ti-file-type-ppt",  iconClass: "ppt", label: "PPT"  },
  PPTX: { icon: "ti-file-type-ppt",  iconClass: "ppt", label: "PPTX" },
  JPG:  { icon: "ti-photo",          iconClass: "img", label: "JPG"  },
  PNG:  { icon: "ti-photo",          iconClass: "img", label: "PNG"  },
  TXT:  { icon: "ti-file-text",      iconClass: "txt", label: "TXT"  },
};

export function getFileTypeMeta(fileType: string): FileTypeMeta {
  return FILE_TYPE_META[fileType?.toUpperCase()] ?? { icon: "ti-file", iconClass: "txt", label: fileType };
}

// ─── Category metadata ────────────────────────────────────────────────────────

export const CATEGORY_META: Record<DocCategory, { label: string; color: string; bg: string; icon: string }> = {
  policy:   { label: "Policy",   color: "var(--primary)", bg: "rgba(124,58,237,0.10)",  icon: "ti-shield-check"    },
  form:     { label: "Form",     color: "var(--info)",    bg: "rgba(37,99,235,0.10)", icon: "ti-file-description" },
  template: { label: "Template", color: "var(--success)", bg: "rgba(23,144,90,0.10)", icon: "ti-table"            },
  other:    { label: "Other",    color: "var(--outline)", bg: "var(--bg-low)",          icon: "ti-file"             },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

export function formatUploadedAt(iso: string): string {
  return formatDate(iso);
}

// Accepted MIME types for the file input
export const DOC_ACCEPT =
  ".pdf,application/pdf," +
  ".doc,application/msword," +
  ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document," +
  ".xls,application/vnd.ms-excel," +
  ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet," +
  ".ppt,application/vnd.ms-powerpoint," +
  ".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation," +
  ".jpg,.jpeg,image/jpeg," +
  ".png,image/png," +
  ".txt,text/plain," +
  ".csv,text/csv";
