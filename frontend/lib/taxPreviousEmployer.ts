// Tax a previous employer deducted cannot exceed the income they paid (UAT-053). Same rule as the server's
// tax_declaration_validation; the message is shown beside the TDS field as soon as the numbers disagree.

export const PREVIOUS_TDS_ERROR = "Tax deducted cannot be more than the income paid by that employer.";

/** An error for the previous-employer TDS field, or null when the two amounts are consistent (blank counts as 0). */
export function previousEmployerTdsError(income: string, tds: string): string | null {
  const paid = Number(income || 0);
  const deducted = Number(tds || 0);
  if (!Number.isFinite(paid) || !Number.isFinite(deducted)) return null; // a non-number is the number field's own problem
  return deducted > paid ? PREVIOUS_TDS_ERROR : null;
}
