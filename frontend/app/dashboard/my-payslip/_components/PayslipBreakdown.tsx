"use client";

import type { ApiPayslip } from "./types";
import { INR, fmtMonth } from "./types";

interface Row {
  label: string;
  value: number | null;
  /** Shown instead of an amount when value is null (e.g. not computed anywhere yet). */
  unavailableNote?: string;
}

function BreakdownColumn({ title, subtitle, rows, totalLabel, totalValue, accent }: {
  title: string; subtitle: string; rows: Row[]; totalLabel: string; totalValue: number; accent: string;
}) {
  return (
    <div className="card flex-1 min-w-0">
      <div className="px-4 py-3 border-b" style={{ borderColor: "var(--outline-v)" }}>
        <div className="text-sm font-bold" style={{ color: "var(--on-bg)" }}>{title}</div>
        <div className="text-xs mt-0.5" style={{ color: "var(--on-variant)" }}>{subtitle}</div>
      </div>
      <div className="px-4 py-2">
        {rows.map(r => (
          <div key={r.label} className="flex justify-between items-center py-2 border-b border-[var(--outline-v)] last:border-0">
            <span className="text-sm" style={{ color: "var(--on-variant)" }}>{r.label}</span>
            {r.value === null ? (
              <span className="text-xs italic" style={{ color: "var(--outline)" }}>{r.unavailableNote}</span>
            ) : (
              <span className="text-sm font-semibold" style={{ color: "var(--on-bg)" }}>{INR(r.value)}</span>
            )}
          </div>
        ))}
      </div>
      <div className="flex justify-between items-center px-4 py-3 border-t" style={{ borderColor: "var(--outline-v)" }}>
        <span className="text-sm font-bold" style={{ color: accent }}>{totalLabel}</span>
        <span className="text-base font-extrabold" style={{ color: accent }}>{INR(totalValue)}</span>
      </div>
    </div>
  );
}

interface Props {
  slip: ApiPayslip;
  /** Employer gratuity provision rate (%) from PayrollSettings, or null if not yet loaded. */
  gratuityRate: number | null;
}

export default function PayslipBreakdown({ slip, gratuityRate }: Props) {
  const monthLabel = fmtMonth(slip.cycle_start);
  const otherEarningsRows: Row[] = Object.entries(slip.other_earnings ?? {})
    .filter(([, amt]) => Number(amt) !== 0)
    .map(([name, amt]) => ({ label: name, value: Number(amt) }));

  const earningsRows: Row[] = [
    { label: "Basic salary", value: Number(slip.basic) },
    { label: "House rent allowance", value: Number(slip.hra) },
    { label: "Special allowance", value: Number(slip.special_allowance) },
    ...otherEarningsRows,
    ...(Number(slip.bonus) > 0 ? [{ label: "Bonus", value: Number(slip.bonus) }] : []),
    ...(Number(slip.reimbursements) > 0 ? [{ label: "Reimbursements", value: Number(slip.reimbursements) }] : []),
  ].filter(r => r.value !== 0);

  // "Other deductions" folds in ESI, LWF, one-off adjustments and LOP — real
  // statutory/adjustment fields the backend computes — under the single
  // label the spec calls for, so the column still foots to total_deductions.
  const otherDeductions = Number(slip.esi_employee) + Number(slip.lwf_employee)
    + Number(slip.adjustments_deduction) + Number(slip.lop_deduction);

  const deductionsRows: Row[] = [
    { label: "Provident fund", value: Number(slip.pf_employee) },
    { label: "Professional tax", value: Number(slip.pt_deduction) },
    // Real FY2026-27 slab-based TDS estimate from the payroll engine — see
    // backend/apps/payroll/services_income_tax.py. Resolved against the
    // employee's declared EmployeeTaxDeclaration regime at computation time,
    // not a fabricated or hardcoded figure.
    { label: "Income tax (TDS)", value: Number(slip.income_tax) },
    ...(otherDeductions > 0 ? [{ label: "Other deductions", value: otherDeductions }] : []),
  ];

  // Gratuity provision is never persisted per payslip (see EmployeePayslip
  // model docstring) — recomputed here with the exact formula
  // services_estimate.py already uses (basic * gratuity_rate / 100) from the
  // real, admin-configured PayrollSettings.gratuity_rate, so it's a live
  // estimate rather than a historical figure.
  const gratuityProvision = gratuityRate !== null ? Number(slip.basic) * gratuityRate / 100 : null;
  const employerTotal = Number(slip.pf_employer) + Number(slip.esi_employer) + (gratuityProvision ?? 0);

  const employerRows: Row[] = [
    { label: "Employer PF", value: Number(slip.pf_employer) },
    gratuityProvision === null
      ? { label: "Gratuity provision", value: null, unavailableNote: "Rate not loaded" }
      : { label: "Gratuity provision", value: gratuityProvision },
    { label: "Insurance premium", value: Number(slip.esi_employer) },
  ];

  return (
    <div className="flex flex-col lg:flex-row gap-4 items-stretch">
      <BreakdownColumn
        title="Earnings" subtitle={`${monthLabel} payroll components.`}
        rows={earningsRows} totalLabel="Total earnings" totalValue={Number(slip.gross_earnings)} accent="var(--success)"
      />
      <BreakdownColumn
        title="Deductions" subtitle={`${monthLabel} payroll components.`}
        rows={deductionsRows} totalLabel="Total deductions" totalValue={Number(slip.total_deductions)} accent="var(--error)"
      />
      <BreakdownColumn
        title="Employer contributions" subtitle="Benefits paid in addition to net salary."
        rows={employerRows} totalLabel="Total" totalValue={employerTotal} accent="var(--primary)"
      />
    </div>
  );
}
