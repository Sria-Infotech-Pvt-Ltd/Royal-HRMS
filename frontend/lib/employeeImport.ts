import type { ImportCommitResult, ImportInviteProgress, ImportJobProgress, ImportJobStatus, ImportRowStatus } from "@/types/employeeImport";

export const IMPORT_MAX_BYTES = 5 * 1024 * 1024;

/** Quick client-side check before upload; the server repeats it (and the real checks) regardless. */
export function validateImportFile(file: { name: string; size: number }): string | null {
  if (!file.name.toLowerCase().endsWith(".xlsx")) return "Please upload the .xlsx template. CSV files are not accepted here.";
  if (file.size > IMPORT_MAX_BYTES) return "The file is too large. The maximum size is 5 MB.";
  if (file.size === 0) return "The file is empty.";
  return null;
}

export const ROW_STATUS_LABEL: Record<ImportRowStatus, string> = {
  valid: "Valid",
  invalid: "Invalid",
  duplicate: "Duplicate",
};

/** One line describing what happened after a confirmed import; invitations are sent in the background, so progress may still be running. */
export function describeCommitResult(result: ImportCommitResult, progress: ImportInviteProgress | null = null): string {
  const people = `${result.created} employee${result.created === 1 ? "" : "s"}`;
  if (result.already_committed) {
    return `This import was already completed earlier: ${people} were created. Nothing new was added.`;
  }
  const created = `${people} created.`;
  if (!progress) return `${created} Activation emails are being sent.`;
  const failed = progress.failed.length;
  if (progress.state === "sending") return `${created} Sending activation emails: ${progress.sent + failed} of ${progress.total} done.`;
  if (failed === 0) return `${created} Activation emails were sent to all of them.`;
  return `${created} ${failed} activation email${failed === 1 ? "" : "s"} could not be sent: the employees exist, use Resend Invite for them.`;
}

// ── Background import job ─────────────────────────────────────────────────────────────────────────────────────────────────

export const JOB_STATUS_LABEL: Record<ImportJobStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  completed_with_errors: "Completed with errors",
  failed: "Stopped",
  cancelled: "Cancelled",
};

const FAILURE_REASON: Record<string, string> = {
  employee_id_range_full: "the employee ID range for this employment type is full",
  batch_failed: "a batch could not be saved after several attempts",
  file_unreadable: "the stored file could not be read",
};

export const POLL_ACTIVE_MS = 3_000;
export const POLL_WAITING_FOR_EMAILS_MS = 10_000;

/** Emails that are still on their way: waiting in the queue or being sent right now. */
export function emailsInFlight(job: ImportJobProgress): number {
  return job.invitations.pending + job.invitations.processing;
}

/** How long to wait before asking again: quickly while employees are being created, slowly while only emails remain, never when settled. */
export function pollDelayMs(job: ImportJobProgress): number | null {
  if (job.is_active) return POLL_ACTIVE_MS;
  if (emailsInFlight(job) > 0 && !job.invitations.held) return POLL_WAITING_FOR_EMAILS_MS;
  return null;
}

export const canCancelJob = (job: ImportJobProgress): boolean => job.is_active && !job.cancel_requested;
export const canRetryEmails = (job: ImportJobProgress): boolean => job.invitations.failed > 0;
export const hasRowErrors = (job: ImportJobProgress): boolean => job.failed_rows > 0;

const people = (count: number): string => `${count} employee${count === 1 ? "" : "s"}`;

/** Headline about EMPLOYEE CREATION only. Whether the emails arrived is a separate statement (describeEmails). */
export function describeJob(job: ImportJobProgress): string {
  const failed = job.failed_rows > 0 ? `, ${job.failed_rows} row${job.failed_rows === 1 ? "" : "s"} failed` : "";
  switch (job.status) {
    case "queued":
      return "Import queued. The employees will be created in the background. You can close this window: progress is saved.";
    case "running":
      return job.cancel_requested
        ? `Stopping after the current batch. ${people(job.created)} created so far.`
        : `Creating employees: ${job.processed_rows} of ${job.total_rows} rows processed, ${job.created} created${failed}.`;
    case "completed":
      return `${people(job.created)} created.`;
    case "completed_with_errors":
      return `${people(job.created)} created. ${job.failed_rows} row${job.failed_rows === 1 ? "" : "s"} could not be imported: download the error report.`;
    case "cancelled":
      return `Import cancelled. ${people(job.created)} had already been created and stay in the system.`;
    default: {
      const reason = FAILURE_REASON[job.failure_code] ?? "an unexpected problem";
      return `The import stopped because ${reason}. ${people(job.created)} had been created before it stopped.`;
    }
  }
}

/** Headline about EMAIL DELIVERY only. "Sent" means the mail server accepted the message; it does not prove the inbox received it. */
export function describeEmails(job: ImportJobProgress): string {
  const { held, total, sent, failed, skipped } = job.invitations;
  const waiting = emailsInFlight(job);
  if (total === 0) return job.is_active ? "Activation emails are queued after each employee is created." : "No activation emails were needed.";
  const parts = [`${sent} sent`, `${waiting} waiting`, `${failed} failed`];
  if (skipped > 0) parts.push(`${skipped} not needed`);
  const base = `Activation emails: ${parts.join(", ")}.`;
  if (held && waiting > 0) return `${base} Sending is switched off by an administrator, so they are waiting.`;
  if (failed > 0) return `${base} The employees exist; retry the failed emails below.`;
  return base;
}
