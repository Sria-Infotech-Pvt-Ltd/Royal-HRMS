// AIRA-UAT-003: when a bulk import's response never reaches the browser (dropped connection, timeout, session
// expiry) the user must still be told what happened on the server and whether uploading again is safe.

export type BulkImportState = "not_received" | "in_progress" | "interrupted" | "completed"

export interface BulkImportStatus {
  state: BulkImportState
  total_rows?: number | null
  created?: number | null
  skipped?: number | null
  failed?: number | null
  created_since_start?: number | null
}

export function describeBulkImportOutcome(status: BulkImportStatus | null): string {
  if (!status) {
    return "The connection was lost and the import status could not be checked. Refresh the employee list to see which employees were created before uploading again; rows whose email already exists are skipped, so a second upload will not create duplicates.";
  }
  switch (status.state) {
    case "not_received":
      return "The import never reached the server, so no employees were created. It is safe to upload the file again.";
    case "completed":
      return `The import finished on the server: ${status.created ?? 0} created, ${status.skipped ?? 0} skipped, ${status.failed ?? 0} failed out of ${status.total_rows ?? 0} rows. Refresh the employee list to see them. Do not upload the same file again.`;
    case "in_progress":
      return `The import is still running on the server (${status.created_since_start ?? 0} employees created so far). Wait a minute and refresh the employee list before doing anything else.`;
    default:
      return `The import was interrupted before it finished. About ${status.created_since_start ?? 0} of ${status.total_rows ?? 0} employees were created. It is safe to upload the same file again: rows whose email already exists are skipped.`;
  }
}
