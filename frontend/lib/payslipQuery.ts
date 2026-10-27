// My Payslips → payslip queries: client-side helpers. The backend
// (POST /payroll/queries/) stays the authority on eligibility; these only
// decide what to show and give early feedback.

export const QUERY_MAX_LENGTH = 2000;

export interface PayslipQueryRow {
  id: string;
  payslip: string;
  description: string;
  status: "open" | "resolved";
  resolution_note: string;
  resolved_by_name: string | null;
  resolved_at: string | null;
  created_at: string;
}

/** Mirrors the backend rule: sent or acknowledged, and the query window still open. */
export function canRaiseQuery(
  slip: { status: string; query_deadline?: string | null },
  now: Date = new Date(),
): { allowed: boolean; reason: string | null } {
  if (slip.status === "queried") return { allowed: false, reason: "A query on this payslip is already open." };
  if (slip.status !== "sent" && slip.status !== "acknowledged") {
    return { allowed: false, reason: "Queries can be raised once the payslip has been sent to you." };
  }
  if (slip.query_deadline && now.getTime() > new Date(slip.query_deadline).getTime()) {
    return { allowed: false, reason: "The query window for this payslip has closed." };
  }
  return { allowed: true, reason: null };
}

/** null when acceptable, else the problem. */
export function validateQueryText(text: string): string | null {
  const t = text.trim();
  if (!t) return "Please describe your query.";
  if (t.length > QUERY_MAX_LENGTH) return `Please keep the query under ${QUERY_MAX_LENGTH} characters.`;
  return null;
}

/** This payslip's queries, newest first. */
export function queriesFor(rows: PayslipQueryRow[] | null | undefined, payslipId: string): PayslipQueryRow[] {
  return (rows ?? [])
    .filter(q => q.payslip === payslipId)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

export const QUERY_STATUS_LABEL: Record<PayslipQueryRow["status"], string> = { open: "Open", resolved: "Resolved" };
