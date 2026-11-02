// Presentation of a SAVED payslip in the standard and wage-slip layouts.
// Nothing here recalculates payroll: every total shown reconciles to the
// stored figures (gross_earnings, total_deductions, net_pay).
//
// Payroll stores components at their full monthly value and LOP as one
// deduction. The wage slip instead shows each component's "Actual" (full
// month) and "Earning" (for the days paid): LOP is split across the
// components in proportion, rounded to rupees, with any rounding difference
// put on the largest component — so the Earning column always totals
// exactly the full components minus the saved LOP.

export interface AdjustmentItem {
  type: "addition" | "deduction" | "arrear";
  label: string;
  amount: string;
}

export interface PayslipAmounts {
  basic: string;
  hra: string;
  special_allowance: string;
  other_earnings: Record<string, number>;
  other_deductions?: Record<string, number>;
  bonus: string;
  reimbursements: string;
  gross_earnings: string;
  lop_deduction: string;
  pf_employee: string;
  esi_employee: string;
  pt_deduction: string;
  lwf_employee: string;
  adjustments_earning?: string;
  adjustments_deduction?: string;
  adjustment_items?: AdjustmentItem[];
  total_deductions: string;
  net_pay: string;
}

export interface AmountRow { label: string; amount: number }
export interface WageSlipEarning { label: string; actual: number | null; earned: number }

const num = (v: unknown) => {
  const n = Number(v ?? 0);
  return Number.isFinite(n) ? n : 0;
};

/** Salary components that make up the processed gross (full-month values). */
export function componentRows(slip: PayslipAmounts): AmountRow[] {
  const rows: AmountRow[] = [
    { label: "Basic", amount: num(slip.basic) },
    { label: "HRA", amount: num(slip.hra) },
    { label: "Special Allowance", amount: num(slip.special_allowance) },
    ...Object.entries(slip.other_earnings ?? {}).map(([label, amount]) => ({ label, amount: num(amount) })),
  ];
  return rows.filter((r, i) => i === 0 || r.amount !== 0);
}

/** Split `lop` across `actuals` (rupees). Sum = round(sum(actuals) - lop), never below 0. */
export function splitLop(actuals: number[], lop: number): number[] {
  const total = actuals.reduce((a, b) => a + b, 0);
  if (total <= 0) return actuals.map(() => 0);
  const target = Math.max(0, Math.round(total - Math.max(0, lop)));
  const factor = target / total;
  const earned = actuals.map(a => Math.round(a * factor));
  const diff = target - earned.reduce((a, b) => a + b, 0);
  if (diff !== 0) {
    let largest = 0;
    actuals.forEach((a, i) => { if (a > actuals[largest]) largest = i; });
    earned[largest] += diff;
  }
  return earned;
}

/** One-time adjustments of one kind, itemised when the payslip saved the
 *  items, else (older payslips) one line for the saved total. */
export function adjustmentRows(slip: PayslipAmounts, kind: "earning" | "deduction"): AmountRow[] {
  const items = (slip.adjustment_items ?? []).filter(i =>
    kind === "deduction" ? i.type === "deduction" : i.type !== "deduction");
  if (items.length > 0) return items.map(i => ({ label: i.label, amount: num(i.amount) }));
  const total = num(kind === "deduction" ? slip.adjustments_deduction : slip.adjustments_earning);
  return total ? [{ label: kind === "deduction" ? "Other deductions" : "Additions", amount: total }] : [];
}

/** True when additions are paid on top of the saved gross (payslip as
 *  processed); false once gross was recomputed to include them (after the
 *  reimbursement / bonus step). Either way net_pay is the saved value. */
export function additionsOutsideGross(slip: PayslipAmounts): boolean {
  const additions = num(slip.adjustments_earning);
  if (!additions) return false;
  const components = componentRows(slip).reduce((a, r) => a + r.amount, 0);
  const inside = components + num(slip.bonus) + num(slip.reimbursements) + additions;
  return Math.abs(num(slip.gross_earnings) - inside) > 0.5;
}

export interface WageSlipModel {
  earnings: WageSlipEarning[];
  deductions: AmountRow[];
  totals: { actual: number; earned: number; deductions: number; net: number };
}

export function wageSlipModel(slip: PayslipAmounts, fixedRows: string[] = []): WageSlipModel {
  const components = componentRows(slip);
  const earnedParts = splitLop(components.map(r => r.amount), num(slip.lop_deduction));
  const earnings: WageSlipEarning[] = components.map((r, i) => ({
    label: r.label, actual: Math.round(r.amount), earned: earnedParts[i],
  }));
  if (num(slip.bonus)) earnings.push({ label: "Bonus", actual: null, earned: num(slip.bonus) });
  if (num(slip.reimbursements)) earnings.push({ label: "Reimbursement", actual: null, earned: num(slip.reimbursements) });
  for (const r of adjustmentRows(slip, "earning")) earnings.push({ label: r.label, actual: null, earned: r.amount });

  const deductions: AmountRow[] = [
    { label: "PF", amount: num(slip.pf_employee) },
    { label: "PT", amount: num(slip.pt_deduction) },
    { label: "ESIC", amount: num(slip.esi_employee) },
    { label: "LWF", amount: num(slip.lwf_employee) },
    ...Object.entries(slip.other_deductions ?? {}).map(([label, amount]) => ({ label, amount: num(amount) })),
    ...adjustmentRows(slip, "deduction"),
  ];
  const present = new Set(deductions.map(d => d.label.toLowerCase()));
  for (const label of fixedRows) {
    if (!present.has(label.toLowerCase())) {
      deductions.push({ label, amount: 0 });
      present.add(label.toLowerCase());
    }
  }

  return {
    earnings,
    deductions,
    totals: {
      actual: Math.round(components.reduce((a, r) => a + r.amount, 0)),
      earned: earnings.reduce((a, e) => a + e.earned, 0),
      // LOP is already taken out of the Earning column, so not repeated here.
      deductions: num(slip.total_deductions) - num(slip.lop_deduction),
      net: num(slip.net_pay),
    },
  };
}

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
const MONTHS_LONG = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
  "OCTOBER", "NOVEMBER", "DECEMBER"];

/** "WAGES SLIP FOR THE MONTH OF SEPTEMBER-2026" for a calendar-month cycle,
 *  otherwise "WAGES SLIP FOR THE PERIOD 24 AUG-26 TO 22 SEP-26". */
export function wageSlipPeriodLabel(cycleStart: string, cycleEnd: string): string {
  const [sy, sm, sd] = cycleStart.split("-").map(Number);
  const [ey, em, ed] = cycleEnd.split("-").map(Number);
  const lastDay = new Date(Date.UTC(sy, sm, 0)).getUTCDate();
  if (sd === 1 && sy === ey && sm === em && ed === lastDay) {
    return `WAGES SLIP FOR THE MONTH OF ${MONTHS_LONG[sm - 1]}-${sy}`;
  }
  const fmt = (y: number, m: number, d: number) => `${d} ${MONTHS[m - 1]}-${String(y).slice(-2)}`;
  return `WAGES SLIP FOR THE PERIOD ${fmt(sy, sm, sd)} TO ${fmt(ey, em, ed)}`;
}
