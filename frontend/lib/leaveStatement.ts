// Display helpers for the backend's monthly leave statement
// (apps/hrms/services_monthly_statement.statement_payload). They only choose
// what to show — every figure comes from the backend; nothing is calculated
// here (no expiry, carry-forward or balances).

import type { LeaveStatement, LeaveStatementMonth } from "@/types/employeeDashboard";

export interface StatementLine {
  key:   "carried_in" | "credit" | "used" | "pending" | "expired" | "closing";
  label: string;
  value: number;
  tone?: "error" | "strong";
}

/** The lines a month card shows. Expiry only exists for no-carry months;
 *  "carried in" only when something was actually carried into the month. */
export function monthLines(m: LeaveStatementMonth): StatementLine[] {
  const lines: StatementLine[] = [];
  if (m.carried_in) lines.push({ key: "carried_in", label: "Carried in", value: m.carried_in });
  lines.push({ key: "credit", label: "Credited", value: m.credit });
  lines.push({ key: "used", label: "Used", value: m.used });
  if (m.pending) lines.push({ key: "pending", label: "Pending", value: m.pending });
  if (m.carry_off) lines.push({ key: "expired", label: "Expired", value: m.expired, tone: m.expired ? "error" : undefined });
  lines.push({ key: "closing", label: "Balance", value: m.closing, tone: "strong" });
  return lines;
}

export function scheduleChip(stmt: LeaveStatement): string {
  return stmt.monthly_carry_forward === false
    ? "Monthly · unused credit expires at month end"
    : "Monthly · unused credit carries forward";
}

/** Notes explaining what the statement does and doesn't contain for this year. */
export function statementNotes(stmt: LeaveStatement, year: number): string[] {
  const notes: string[] = [];
  if (!stmt.months.some(m => m.credit)) notes.push(`No monthly credits are recorded for ${year}.`);
  if (stmt.opening) {
    notes.push(`${stmt.opening} day(s) from opening balance, carry forward or adjustments are included and never expire.`);
  }
  if (stmt.monthly_rules_from) {
    const from = new Date(`${stmt.monthly_rules_from}T00:00:00`);
    if (from.getFullYear() === year && from.getMonth() > 0) {
      notes.push(`The current monthly rules apply from ${from.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}; earlier months aren't recalculated.`);
    } else if (from.getFullYear() > year) {
      notes.push(`Monthly rules apply from ${from.getFullYear()}; this year follows the balance as it was recorded.`);
    }
  }
  if (stmt.used_not_itemised) {
    notes.push(`${stmt.used_not_itemised} day(s) used aren't linked to a month (for example, an imported opening balance).`);
  }
  if (!stmt.reconciled) notes.push("Month-end processing for a past month is still due; the yearly balance is current.");
  return notes;
}

// ─── Annual / Monthly separation (Employee Profile → Leave) ─────────────────

export type ScheduleView = "annual" | "monthly";

/** Split rows by their policy's credit_schedule (from the backend). Rows whose
 *  schedule is unknown (no policy) are kept apart, never guessed into a view. */
export function splitBySchedule<T extends { credit_schedule?: string | null }>(rows: T[]) {
  return {
    annual:       rows.filter(r => r.credit_schedule === "annual"),
    monthly:      rows.filter(r => r.credit_schedule === "monthly"),
    unclassified: rows.filter(r => r.credit_schedule !== "annual" && r.credit_schedule !== "monthly"),
  };
}

/** Month to select by default: the current month for this year, December for a past year, January for a future one. */
export function defaultMonth(year: number, today: Date = new Date()): number {
  if (year < today.getFullYear()) return 12;
  if (year > today.getFullYear()) return 1;
  return today.getMonth() + 1;
}

export function monthOf(stmt: LeaveStatement | null | undefined, month: number): LeaveStatementMonth | null {
  return stmt?.months.find(m => m.month === month) ?? null;
}
