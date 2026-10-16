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
