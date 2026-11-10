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

/** start: choose a file; previewed: the checked file; job: following a background import job (it survives closing the window). */
export type ImportStep = "start" | "previewed" | "job";

export type ImportJobStatus = "queued" | "running" | "completed" | "completed_with_errors" | "failed" | "cancelled";

/** Where the activation emails of one import stand. `held` is true while an administrator has switched invitation emails off. */
export interface ImportJobInvitations {
  held: boolean;
  total: number;
  pending: number;
  processing: number;
  sent: number;
  skipped: number;
  failed: number;
}

/** What GET /employees/bulk-import/jobs/<id>/ returns (and POST .../jobs/ on creation). Employee creation and email delivery are separate. */
export interface ImportJobProgress {
  job_id: string;
  status: ImportJobStatus;
  is_active: boolean;
  file_name: string;
  total_rows: number;
  processed_rows: number;
  created: number;
  failed_rows: number;
  percent: number;
  cancel_requested: boolean;
  failure_code: string;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  invitations: ImportJobInvitations;
  invitation_failures: ImportInviteFailure[];
}

export interface ImportInvitesRetryResult {
  requeued: number;
  dispatched: number;
}
