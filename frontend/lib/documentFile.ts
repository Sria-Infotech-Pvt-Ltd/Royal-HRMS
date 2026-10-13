// Rules for documents employees upload (ESS Documents tab and tax proofs). The server enforces the
// same type and size limits — these checks just tell the employee straight away.

export const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
export const MAX_FILE_SIZE_LABEL = "5 MB";
export const ACCEPTED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];
export const ACCEPTED_TYPES_LABEL = "PDF, JPG or PNG";

export function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const PREVIEW_LIFETIME_MS = 60_000;

/** Opens a picked (not yet uploaded) file in a new tab so the person can check it is the right one. */
export function openFilePreview(file: File): void {
  const url = URL.createObjectURL(file);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), PREVIEW_LIFETIME_MS);
}

/** Returns what is wrong with the file, or null if it can be uploaded. */
export function validateDocumentFile(file: File): string | null {
  const lowerName = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some(extension => lowerName.endsWith(extension))) {
    return `Unsupported file type. Please choose a ${ACCEPTED_TYPES_LABEL} file.`;
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `File is too large (${formatFileSize(file.size)}). Maximum allowed size is ${MAX_FILE_SIZE_LABEL}.`;
  }
  return null;
}
