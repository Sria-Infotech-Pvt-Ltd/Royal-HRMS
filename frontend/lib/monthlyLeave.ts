// Monthly Leave Management (Settings → Leave Management) — shared types and
// pure helpers. The backend (apps/hrms/services_leave_credit.set_monthly_credit)
// is the source of truth for every rule; these only give early feedback.

export const MAX_MONTHLY_CREDIT = 31;

export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export type ImportRowStatus = "new" | "update" | "unchanged" | "duplicate" | "error";

export interface MonthlyImportRow {
  row:              number;
  employee_code:    string;
  employee_name:    string | null;
  leave_type:       string;
  leave_type_label: string | null;
  credit:           number | string;
  previous:         number | null;
  delta:            number | null;
  status:           ImportRowStatus;
  message:          string;
}

export interface MonthlyImportPreview {
  year:  number;
  month: number;
  rows:  MonthlyImportRow[];
  counts: Record<ImportRowStatus, number>;
  annual_entitlements: Record<string, number>;
}

export interface MonthlyImportResult {
  year:  number;
  month: number;
  rows:  MonthlyImportRow[];
  summary: { created: number; updated: number; skipped: number; failed: number; total: number };
  annual_entitlements: Record<string, number>;
}

export interface MonthlyLeaveTypeRow {
  leave_type:       string;
  leave_type_label: string;
  annual_days:      number;
  monthly_credit:   number;
  balance: { total: number; used: number; pending: number; available: number } | null;
}

/** Years HR can credit: the current calendar year and the two before it. */
export function creditYears(today: Date = new Date()): number[] {
  const y = today.getFullYear();
  return [y, y - 1, y - 2];
}

/** Returns an error message, or null when the value is an acceptable monthly credit. */
export function validateMonthlyCredit(raw: string): string | null {
  const text = raw.trim();
  if (!text) return "Enter a monthly leave credit (0 removes the month's credit).";
  if (!/^\d+(\.\d)?$/.test(text)) {
    return /^-/.test(text)
      ? "Monthly leave credit cannot be negative."
      : "Use a number with at most one decimal place, e.g. 1 or 1.5.";
  }
  if (Number(text) > MAX_MONTHLY_CREDIT) return `Monthly leave credit cannot exceed ${MAX_MONTHLY_CREDIT} days.`;
  return null;
}

/** Balance after saving `next` in place of the month's current credit. */
export function projectedBalance(row: MonthlyLeaveTypeRow, next: number) {
  const delta = next - row.monthly_credit;
  const total = (row.balance?.total ?? 0) + delta;
  const used = row.balance?.used ?? 0;
  return { delta, total, available: total - used };
}

/** Leave types in the rows that also carry an annual entitlement (double-counting warning). */
export function annualWarningTypes(rows: MonthlyImportRow[], annual: Record<string, number>): string[] {
  const labels = new Set<string>();
  for (const r of rows) {
    if ((r.status === "new" || r.status === "update") && annual[r.leave_type]) {
      labels.add(`${r.leave_type_label ?? r.leave_type} (${annual[r.leave_type]} days/year)`);
    }
  }
  return [...labels];
}

export const STATUS_LABEL: Record<ImportRowStatus, string> = {
  new:       "New",
  update:    "Update",
  unchanged: "Unchanged",
  duplicate: "Duplicate",
  error:     "Error",
};

export interface MonthlyAssignment {
  employee_id:      string;
  employee_name:    string;
  branch:           string;
  is_active:        boolean;
  leave_type:       string;
  leave_type_label: string;
  year:             number;
  month:            number;
  credit:           number;
  last_updated:     string;
}

export interface MonthlyAssignmentsResponse {
  year:        number;
  month:       number;
  assignments: MonthlyAssignment[];
  summary:     { employees: number; entries: number; total_days: number };
}

const round1 = (n: number) => Math.round(n * 10) / 10;

/** Confirmation text for changing a month's credit from `previous` to `next` days. */
export function describeChange(previous: number, next: number): string {
  const delta = round1(next - previous);
  if (delta === 0) return "No change.";
  if (next === 0) return `Removes this month's credit: ${previous} day(s) will be taken off the employee's balance.`;
  return delta > 0
    ? `Changes ${previous} → ${next} day(s): ${delta} day(s) will be added to the employee's balance.`
    : `Changes ${previous} → ${next} day(s): ${-delta} day(s) will be taken off the employee's balance.`;
}

/** An employee row in the Manual Entry checklist (from the scoped /employees/ list). */
export interface PickableEmployee {
  uuid:        string;
  employee_id: string;
  full_name:   string;
  branch:      string;
  department:  string;
  is_active:   boolean;
}

/** Why a row can't be ticked, or null when it can. */
export function unselectableReason(emp: PickableEmployee, currentUserId: string | null | undefined): string | null {
  if (!emp.is_active) return "inactive";
  if (currentUserId && emp.uuid === currentUserId) return "you";
  return null;
}

/** State of the Select All box for the rows currently shown. */
export function selectAllState(rows: PickableEmployee[], selected: Set<string>, currentUserId?: string | null) {
  const selectable = rows.filter(r => !unselectableReason(r, currentUserId));
  const ticked = selectable.filter(r => selected.has(r.employee_id)).length;
  return { selectable: selectable.length, checked: selectable.length > 0 && ticked === selectable.length,
           indeterminate: ticked > 0 && ticked < selectable.length };
}

/** Tick or untick every selectable row currently shown; other selections are kept. */
export function toggleAllShown(
  rows: PickableEmployee[], selected: Map<string, PickableEmployee>, check: boolean, currentUserId?: string | null,
): Map<string, PickableEmployee> {
  const next = new Map(selected);
  for (const r of rows) {
    if (unselectableReason(r, currentUserId)) continue;
    if (check) next.set(r.employee_id, r);
    else next.delete(r.employee_id);
  }
  return next;
}
