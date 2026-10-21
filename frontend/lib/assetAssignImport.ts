// Settings → Assets → Bulk Assign — client-side helpers. The backend
// (apps/assets/services_assign_import.py) validates every row; file checks,
// error text and the report download are shared with Bulk Import (lib/assetImport).

/** Mirrors services_assign_import.COLUMNS (same order as the templates). */
export const ASSET_ASSIGN_COLUMNS: { header: string; required: boolean }[] = [
  { header: "Asset Tag", required: true },
  { header: "Employee ID", required: true },
  { header: "Assigned Date", required: true },
  { header: "Condition at Assignment", required: true },
  { header: "Expected Return Date", required: false },
  { header: "Remarks", required: false },
];

export type AssignRowStatus = "ready" | "assigned" | "already_assigned" | "error";

export interface AssetAssignRow {
  row:           number;
  asset_tag:     string;
  asset_name:    string;
  employee_id:   string;
  employee_name: string;
  status:        AssignRowStatus;
  errors:        { column: string; message: string }[];
}

export interface AssetAssignPreview {
  rows:   AssetAssignRow[];
  counts: { ready: number; already_assigned: number; error: number };
  error_report_csv: string | null;
}

export interface AssetAssignResult {
  rows:    AssetAssignRow[];
  summary: { total: number; assigned: number; already_assigned: number; failed: number; skipped: number };
  error_report_csv: string | null;
}

export const ASSIGN_STATUS_LABEL: Record<AssignRowStatus, string> = {
  ready:            "Ready",
  assigned:         "Assigned",
  already_assigned: "Already assigned",
  error:            "Error",
};

/** "Asset name (TAG) → Employee name (ID)", falling back to what the file said. */
export function mappingText(r: AssetAssignRow): { asset: string; employee: string } {
  return {
    asset:    r.asset_name ? `${r.asset_name} (${r.asset_tag})` : r.asset_tag || "—",
    employee: r.employee_name ? `${r.employee_name} (${r.employee_id})` : r.employee_id || "—",
  };
}
