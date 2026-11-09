export type ImportRowStatus = "valid" | "invalid" | "duplicate";

export interface ImportPreviewRow {
  row: number;
  status: ImportRowStatus;
  is_valid: boolean;
  errors: string[];
  // Non-sensitive columns only, keyed by column key (first_name, email, ...).
  values: Record<string, string>;
}

export interface ImportSummary {
  total: number;
  valid: number;
  invalid: number;
  duplicate: number;
}

export interface ImportPreview {
  batch_id: string;
  file_hash: string;
  summary: ImportSummary;
  can_import: boolean;
  allowed_branches: string[];
  rows: ImportPreviewRow[];
}

export interface ImportInviteFailure {
  row: number;
  employee_id: string;
  reason: string;
}

export interface ImportInviteProgress {
  batch_id: string;
  state: "sending" | "done";
  total: number;
  sent: number;
  failed: ImportInviteFailure[];
}

export interface ImportCommitResult {
  batch_id: string;
  created: number;
  already_committed: boolean;
  invites_total?: number;
  invites_sent: number | null;
  invite_failures: ImportInviteFailure[];
  employees?: { employee_id: string; name: string }[];
}

export type ImportStep = "start" | "previewed" | "done";
