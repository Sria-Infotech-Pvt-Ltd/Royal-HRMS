// Settings → Assets → Bulk Import — client-side helpers. The backend
// (apps/assets/services_import.py) validates every row; these only give
// early feedback and format results.

export const ASSET_IMPORT_MAX_BYTES = 5 * 1024 * 1024;

/** Mirrors services_import.COLUMNS (required ones marked). */
export const ASSET_IMPORT_COLUMNS: { header: string; required: boolean }[] = [
  { header: "Asset Tag", required: true }, { header: "Asset Name", required: true },
  { header: "Category", required: true }, { header: "Category Other", required: false },
  { header: "Asset Type", required: true }, { header: "Asset Type Other", required: false },
  { header: "Branch", required: true }, { header: "Brand", required: false }, { header: "Model", required: false },
  { header: "Serial Number", required: false }, { header: "Purchase Date", required: false },
  { header: "Purchase Price", required: false }, { header: "Vendor", required: false },
  { header: "Warranty Start Date", required: false }, { header: "Warranty End Date", required: false },
  { header: "Condition", required: false }, { header: "Description", required: false },
];

export type ImportRowStatus = "ready" | "duplicate" | "error" | "created";

export interface AssetImportRow {
  row:        number;
  asset_tag:  string;
  asset_name: string;
  branch:     string;
  status:     ImportRowStatus;
  errors:     { column: string; message: string }[];
}

export interface AssetImportPreview {
  rows:   AssetImportRow[];
  counts: { ready: number; duplicate: number; error: number };
  error_report_csv: string | null;
}

export interface AssetImportResult {
  rows:    AssetImportRow[];
  summary: { total: number; created: number; duplicate: number; failed: number; skipped: number };
  error_report_csv: string | null;
}

/** null when acceptable, else the reason. */
export function checkImportFile(file: { name: string; size: number }): string | null {
  const name = file.name.toLowerCase();
  if (!name.endsWith(".csv") && !name.endsWith(".xlsx")) return "Upload a .csv or .xlsx file.";
  if (file.size > ASSET_IMPORT_MAX_BYTES) return "File must not exceed 5 MB.";
  if (file.size === 0) return "The file is empty.";
  return null;
}

export function errorText(errors: AssetImportRow["errors"]): string {
  return errors.map(e => (e.column ? `${e.column}: ${e.message}` : e.message)).join(" · ");
}

/** Bytes of the base64 error report returned by the API (UTF-8 CSV). */
export function decodeReport(b64: string): Uint8Array<ArrayBuffer> {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
