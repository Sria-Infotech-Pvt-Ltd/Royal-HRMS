"use client";

// "My declaration" card of the Tax tab: regime, review status and what each head is
// worth after the statutory limits. The Declare / Edit action lives in the page header.

import { tr } from "@/lib/i18n/tr";
import type { ApiTaxDeclaration } from "@/types/taxDeclaration";
import { DEDUCTION_HEAD_LABELS, totalDeduction } from "@/lib/taxDeclarationForm";
import { formatDate } from "@/lib/formatDate";

const STATUS_BADGE: Record<string, string> = {
  draft: "badge-neutral", submitted: "badge-warn", approved: "badge-success",
};

function formatInr(amount: number): string {
  return `₹${Math.round(amount).toLocaleString("en-IN")}`;
}

interface Props {
  declaration: ApiTaxDeclaration | null;
  isLoading: boolean;
}

export default function TaxDeclarationSummary({ declaration, isLoading }: Props) {
  const hasStarted = !!declaration && (declaration.status !== "draft" || Object.keys(declaration.declared_investments).length > 0);

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header">
        <div className="card-title"><i className="ti ti-file-invoice" /> {tr("My declaration")}</div>
        {declaration && hasStarted && (
          <span className={`badge ${STATUS_BADGE[declaration.status]}`}>{declaration.status_display}</span>
        )}
      </div>
      <p style={{ margin: "0 24px 8px", fontSize: 12, color: "var(--on-variant)" }}>
        {tr("Submitted declarations are reviewed by Payroll Operations. Proofs go under Documents → Tax proof.")}
      </p>
      {isLoading ? (
        <div className="empty-state"><i className="ti ti-loader-2 spin" /><h3>{tr("Loading declaration…")}</h3></div>
      ) : !declaration || !hasStarted ? (
        <div className="empty-state">
          <i className="ti ti-file-invoice" />
          <h3>{tr("No declaration yet")}</h3>
          <p>{tr("Choose your tax regime and declare your investments so the right tax is deducted from your salary.")}</p>
        </div>
      ) : (
        <div style={{ padding: "4px 24px 16px" }}>
          <div style={{ fontWeight: 600 }}>{tr("FY {year} · {regime}", { year: declaration.financial_year, regime: declaration.tax_regime_display })}</div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 8 }}>
            {declaration.submitted_at ? tr("Submitted {date}", { date: formatDate(declaration.submitted_at) }) : tr("Saved as a draft — not sent to payroll yet")}
            {declaration.approved_by_name && tr(" · Approved by {name}", { name: declaration.approved_by_name })}
          </div>
          {declaration.tax_regime === "old" ? <DeductionRows declaration={declaration} /> : (
            <div style={{ fontSize: 13, color: "var(--on-variant)" }}>
              {tr("New regime: only the standard deduction applies, so there is nothing else to claim.")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DeductionRows({ declaration }: { declaration: ApiTaxDeclaration }) {
  const rows = DEDUCTION_HEAD_LABELS.filter(head => (declaration.deduction_summary[head.key] ?? 0) > 0);
  const isRentPending = !!declaration.declared_investments._details?.hra && (declaration.deduction_summary.HRA ?? 0) === 0;
  if (rows.length === 0 && !isRentPending) {
    return <div style={{ fontSize: 13, color: "var(--on-variant)" }}>{tr("No deductions declared yet.")}</div>;
  }
  return (
    <div>
      {rows.map(head => (
        <div key={head.key} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--outline-v)", fontSize: 13 }}>
          <span>{tr(head.label)}</span>
          <span style={{ fontWeight: 600 }}>{formatInr(declaration.deduction_summary[head.key])}</span>
        </div>
      ))}
      {isRentPending && (
        <div style={{ padding: "6px 0", fontSize: 12.5, color: "var(--on-variant)" }}>
          {tr("Rent declared — your HRA exemption is worked out by payroll from your salary when it is processed.")}
        </div>
      )}
      <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0 0", fontSize: 13, fontWeight: 700 }}>
        <span>{tr("Total deduction after limits")}</span>
        <span>{formatInr(totalDeduction(declaration))}</span>
      </div>
    </div>
  );
}
