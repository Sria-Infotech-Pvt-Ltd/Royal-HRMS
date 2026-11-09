export interface ReportFilterOption {
  value: string;
  label: string;
}

export interface ReportFilter {
  key: string;
  label: string;
  kind: "select" | "date";
  default: string;
  options: ReportFilterOption[];
}

export interface ReportDefinition {
  key: string;
  title: string;
  description: string;
  filters: ReportFilter[];
  /** Columns left out of an emailed copy (contact details). */
  email_omits: string[];
}

export interface ReportCatalog {
  reports: ReportDefinition[];
  limits: { max_recipients: number; max_note_length: number; max_rows: number };
}

export interface ReportPreview {
  headers: string[];
  rows: string[][];
  row_count: number;
}

export interface ReportRecipient {
  id: string;
  employee_id: string;
  name: string;
  designation: string;
}

export type ReportFilterValues = Record<string, string>;
