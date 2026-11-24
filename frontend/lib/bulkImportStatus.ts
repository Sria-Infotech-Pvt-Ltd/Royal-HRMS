// AIRA-UAT-003: when a bulk import's response never reaches the browser (dropped connection, timeout, session
// expiry) the user must still be told what happened on the server and whether uploading again is safe.
import { tr } from "@/lib/i18n/tr";

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
    return tr("The connection was lost and the import status could not be checked. Refresh the employee list to see which employees were created before uploading again; rows whose email already exists are skipped, so a second upload will not create duplicates.");
  }
  switch (status.state) {
    case "not_received":
      return tr("The import never reached the server, so no employees were created. It is safe to upload the file again.");
    case "completed":
      return tr("The import finished on the server: {created} created, {skipped} skipped, {failed} failed out of {total} rows. Refresh the employee list to see them. Do not upload the same file again.", { created: status.created ?? 0, skipped: status.skipped ?? 0, failed: status.failed ?? 0, total: status.total_rows ?? 0 });
    case "in_progress":
      return tr("The import is still running on the server ({created} employees created so far). Wait a minute and refresh the employee list before doing anything else.", { created: status.created_since_start ?? 0 });
    default:
      return tr("The import was interrupted before it finished. About {created} of {total} employees were created. It is safe to upload the same file again: rows whose email already exists are skipped.", { created: status.created_since_start ?? 0, total: status.total_rows ?? 0 });
  }
}
