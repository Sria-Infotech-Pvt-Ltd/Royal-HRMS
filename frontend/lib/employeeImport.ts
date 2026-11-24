import { tr } from "@/lib/i18n/tr";
import type { ImportCommitResult, ImportInviteProgress, ImportJobProgress, ImportJobStatus, ImportRowStatus } from "@/types/employeeImport";

export const IMPORT_MAX_BYTES = 5 * 1024 * 1024;

/** Quick client-side check before upload; the server repeats it (and the real checks) regardless. */
export function validateImportFile(file: { name: string; size: number }): string | null {
  if (!file.name.toLowerCase().endsWith(".xlsx")) return tr("Please upload the .xlsx template. CSV files are not accepted here.");
  if (file.size > IMPORT_MAX_BYTES) return tr("The file is too large. The maximum size is 5 MB.");
  if (file.size === 0) return tr("The file is empty.");
  return null;
}

export const ROW_STATUS_LABEL: Record<ImportRowStatus, string> = {
  valid: "Valid",
  invalid: "Invalid",
  duplicate: "Duplicate",
};

/** One line describing what happened after a confirmed import; invitations are sent in the background, so progress may still be running. */
export function describeCommitResult(result: ImportCommitResult, progress: ImportInviteProgress | null = null): string {
  const names = people(result.created);
  if (result.already_committed) {
    return tr("This import was already completed earlier: {people} were created. Nothing new was added.", { people: names });
  }
  const created = tr("{people} created.", { people: names });
  if (!progress) return tr("{created} Activation emails are being sent.", { created });
  const failed = progress.failed.length;
  if (progress.state === "sending") {
    return tr("{created} Sending activation emails: {done} of {total} done.", { created, done: progress.sent + failed, total: progress.total });
  }
  if (failed === 0) return tr("{created} Activation emails were sent to all of them.", { created });
  return failed === 1
    ? tr("{created} {count} activation email could not be sent: the employees exist, use Resend Invite for them.", { created, count: failed })
    : tr("{created} {count} activation emails could not be sent: the employees exist, use Resend Invite for them.", { created, count: failed });
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

const people = (count: number): string => (count === 1 ? tr("{count} employee", { count }) : tr("{count} employees", { count }));
const rowsWord = (count: number): string => (count === 1 ? tr("{count} row", { count }) : tr("{count} rows", { count }));

/** The reason text is kept in English in FAILURE_REASON and translated here, where it is shown. */
function failureReason(code: string): string {
  switch (code) {
    case "employee_id_range_full": return tr("the employee ID range for this employment type is full");
    case "batch_failed": return tr("a batch could not be saved after several attempts");
    case "file_unreadable": return tr("the stored file could not be read");
    default: return tr("an unexpected problem");
  }
}

/** Headline about EMPLOYEE CREATION only. Whether the emails arrived is a separate statement (describeEmails). */
export function describeJob(job: ImportJobProgress): string {
  const names = people(job.created);
  switch (job.status) {
    case "queued":
      return tr("Import queued. The employees will be created in the background. You can close this window: progress is saved.");
    case "running":
      if (job.cancel_requested) return tr("Stopping after the current batch. {people} created so far.", { people: names });
      return job.failed_rows > 0
        ? tr("Creating employees: {processed} of {total} rows processed, {created} created, {failed} failed.", { processed: job.processed_rows, total: job.total_rows, created: job.created, failed: rowsWord(job.failed_rows) })
        : tr("Creating employees: {processed} of {total} rows processed, {created} created.", { processed: job.processed_rows, total: job.total_rows, created: job.created });
    case "completed":
      return tr("{people} created.", { people: names });
    case "completed_with_errors":
      return tr("{people} created. {rows} could not be imported: download the error report.", { people: names, rows: rowsWord(job.failed_rows) });
    case "cancelled":
      return tr("Import cancelled. {people} had already been created and stay in the system.", { people: names });
    default:
      return tr("The import stopped because {reason}. {people} had been created before it stopped.", { reason: failureReason(job.failure_code), people: names });
  }
}

/** Headline about EMAIL DELIVERY only. "Sent" means the mail server accepted the message; it does not prove the inbox received it. */
export function describeEmails(job: ImportJobProgress): string {
  const { held, total, sent, failed, skipped } = job.invitations;
  const waiting = emailsInFlight(job);
  if (total === 0) return job.is_active ? tr("Activation emails are queued after each employee is created.") : tr("No activation emails were needed.");
  const parts = [tr("{count} sent", { count: sent }), tr("{count} waiting", { count: waiting }), tr("{count} failed", { count: failed })];
  if (skipped > 0) parts.push(tr("{count} not needed", { count: skipped }));
  const base = tr("Activation emails: {parts}.", { parts: parts.join(", ") });
  if (held && waiting > 0) return tr("{base} Sending is switched off by an administrator, so they are waiting.", { base });
  if (failed > 0) return tr("{base} The employees exist; retry the failed emails below.", { base });
  return base;
}
