// ─── Carry Forward Settings — Leave Policy edit form ──────────────────────────
// Per-policy configuration (how carry forward behaves for one leave type),
// as opposed to the execution types below (running the actual carry-forward
// batch job across employees). Distinct concepts, same feature area.

export type CarryForwardType = "limited" | "unlimited";
export type CarryForwardMode = "automatic" | "manual";

export interface LeavePolicyCarryForwardSettings {
  can_carry_forward: boolean;
  carry_forward_type: CarryForwardType;
  max_carry_forward_days: number;
  carry_forward_mode: CarryForwardMode;
  carry_forward_expiry_days: number; // 0 = never
}

// ─── Carry Forward — Leave Management ─────────────────────────────────────────

// ── Year selection ────────────────────────────────────────────
export interface CarryForwardYearPair {
  from_year: number;
  to_year: number;
}

export interface CarryForwardYearsResponse {
  years: CarryForwardYearPair[];
  default_from: number;
  default_to: number;
}

// ── Preview ───────────────────────────────────────────────────
export interface CarryForwardPreviewRow {
  employee_id: string;
  employee_name: string;
  leave_type: string;
  leave_type_display: string;
  unused_days: number;
  carry_forward_amount: number;
  expiry_date: string | null;
  already_processed: boolean;
}

export interface CarryForwardPreviewResponse {
  from_year: number;
  to_year: number;
  total_rows: number;
  pending_count: number;
  already_processed_count: number;
  preview_rows: CarryForwardPreviewRow[];
}

// ── Run result (audit log entry) ──────────────────────────────
export interface CarryForwardLog {
  id: string;
  from_year: number;
  to_year: number;
  leave_type: string;
  executed_by_name: string;
  process_mode: string;
  total_processed: number;
  total_skipped: number;
  total_failed: number;
  is_completed: boolean;
  notes: string;
  created_at: string; // ISO datetime
}

// ── History (paginated) ───────────────────────────────────────
export interface CarryForwardHistoryResponse {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: CarryForwardLog[];
}

// ── Input ─────────────────────────────────────────────────────
export interface CarryForwardInput {
  from_year: number;
  to_year: number;
}

// ─── Opening Leave Balance Import ──────────────────────────────────────────────
// One-time historical data migration (onboarding an existing company / moving
// off another HRMS). Once run, ongoing balances/carry-forward/allocations are
// owned entirely by the Leave module — this is not a recurring import. There is
// no separate "already imported" status endpoint; per-row duplicate detection
// (see `reason` values below) is what actually prevents re-importing the same
// employee/leave-type/year combination.

export interface OpeningBalanceImportRowError {
  row:            number;
  employee_id:    string;
  leave_type:     string;
  financial_year: string;
  from_date?:     string;
  to_date?:       string;
  reason:         string;
}

export interface OpeningBalanceImportResult {
  total_records:    number;
  balances_created: number;
  history_imported: number;
  successful:       number;
  failed:           number;
  skipped:          number;
  errors:           OpeningBalanceImportRowError[];
  error_report_csv: string | null;
}

export type ImportRowType = "balance" | "history";

export interface ImportPreviewRow {
  row:            number;
  row_type:       ImportRowType;
  employee_id:    string;
  leave_type:     string;
  financial_year: string;
  from_date:      string | null;
  to_date:        string | null;
  days:           string | null;
  valid:          boolean;
  error:          string | null;
}

export interface ImportValidateResult {
  total_rows:   number;
  valid_rows:   number;
  error_rows:   number;
  balance_rows: number;
  history_rows: number;
  preview:      ImportPreviewRow[];
}
