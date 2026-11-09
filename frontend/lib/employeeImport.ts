import type { ImportCommitResult, ImportInviteProgress, ImportRowStatus } from "@/types/employeeImport";

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
