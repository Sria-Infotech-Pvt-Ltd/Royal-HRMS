// Employee dashboard → Leave Balances → monthly breakdown helpers.
// The months are recorded movements (credits, adjustments, leave used), not
// month-end balances; the available balance is always the yearly figure.

import type { LeaveBalance, LeaveMonthRow } from "@/types/employeeDashboard";

const round1 = (n: number) => Math.round(n * 10) / 10;

export interface MonthTotals {
  monthly_credit:    number;
  other_adjustments: number;
  used:              number;
}

export function monthTotals(months: LeaveMonthRow[]): MonthTotals {
  return months.reduce<MonthTotals>(
    (t, m) => ({
      monthly_credit:    round1(t.monthly_credit + m.monthly_credit),
      other_adjustments: round1(t.other_adjustments + m.other_adjustments),
      used:              round1(t.used + m.used),
    }),
    { monthly_credit: 0, other_adjustments: 0, used: 0 },
  );
}

/** Leave types that have something to show month by month (older cached payloads have no `monthly`). */
export function typesWithBreakdown(balances: LeaveBalance[]): LeaveBalance[] {
  return balances.filter(b => (b.statement?.months.length ?? 0) > 0 || (b.monthly?.months.length ?? 0) > 0);
}

export function scheduleLabel(b: LeaveBalance): string {
  if (b.credit_schedule !== "monthly") return "Credited annually";
  return b.monthly_carry_forward === false ? "Credited monthly · no carry forward" : "Credited monthly · carries forward";
}

/** Signed display for an adjustment amount: "+1.5", "-2", "0". */
export function signed(n: number): string {
  return n > 0 ? `+${n}` : String(n);
}
