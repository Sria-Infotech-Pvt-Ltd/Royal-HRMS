"use client";

// Tax declaration — self-service regime choice + declared investment
// amounts, submitted for HR review via a focused "New declaration" modal
// (TaxDeclarationModal.tsx) rather than an always-visible inline edit grid.
//
// YTD TDS is summed from the employee's own real EmployeePayslip.income_tax
// figures for the current financial year (a real slab-based estimate — see
// backend/apps/payroll/services_income_tax.py) rather than fabricated.
//
// The "Proof Window" tile is still shown as "not tracked": no declaration/
// proof-submission deadline field exists on PayrollSettings or anywhere else
// in payroll config.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import TaxDeclarationModal from "./TaxDeclarationModal";
import TaxDeclarationSummary from "./TaxDeclarationSummary";
import TaxHrQueue from "./TaxHrQueue";
import TaxProofsCard from "./TaxProofsCard";
import type { ApiTaxDeclaration } from "@/types/taxDeclaration";
import type { PagedResponse } from "@/app/dashboard/my-payslip/_components/types";
import { currentFinancialYearStart } from "@/app/dashboard/my-payslip/_components/types";

interface PayslipTdsRow {
  cycle_start: string;
  income_tax: string;
}

interface FinancialYearConfig {
  financial_year_start_month: string;
  current_financial_year: string;
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function fyCaption(startMonthName: string, startYear: number): string {
  const startIdx = MONTHS.indexOf(startMonthName);
  if (startIdx === -1) return "";
  const endIdx = (startIdx + 11) % 12;
  return `${MONTHS[startIdx]} ${startYear} – ${MONTHS[endIdx]} ${startYear + 1}`;
}

function formatInr(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
}

interface Props {
  onNavigateToDocuments: () => void;
}

export default function TaxTab({ onNavigateToDocuments }: Props) {
  const canApprove = usePermission("tax_declarations.approve");
  const { data: mine, loading, error, refetch } = useFetch<ApiTaxDeclaration>(API.payroll.myTaxDeclaration);
  const { data: fyConfig } = useFetch<FinancialYearConfig>(API.settings.financialYear);
  // Same source (MyPayslipsView, ordered most-recent-first) the ESS Payslips
  // screen's own YTD summary reads from — see computeYtd() in
  // app/dashboard/my-payslip/_components/types.ts for why the first page
  // already covers the current FY without a separate aggregate endpoint.
  const { data: payslipPage } = useFetch<PagedResponse<PayslipTdsRow>>(API.payroll.myPayslips);

  const [showNewDeclaration, setShowNewDeclaration] = useState(false);

  const ytdTds = (() => {
    const payslips = payslipPage?.results ?? [];
    if (payslips.length === 0) return null;
    const fyStart = currentFinancialYearStart(fyConfig?.financial_year_start_month ?? "April");
    return payslips
      .filter(p => new Date(p.cycle_start) >= fyStart)
      .reduce((sum, p) => sum + Number(p.income_tax), 0);
  })();

  const isLocked = mine?.status === "approved";
  const hasStarted = !!mine && (mine.status !== "draft" || Object.keys(mine.declared_investments).length > 0);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Tax &amp; declarations</div>
          <div className="page-sub">Review your tax information and submit declarations for payroll review.</div>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-filled"
            onClick={() => setShowNewDeclaration(true)}
            disabled={isLocked}
            title={isLocked ? "This financial year's declaration is already approved and can no longer be changed." : undefined}
            suppressHydrationWarning
          >
            <i className={`ti ${hasStarted ? "ti-edit" : "ti-plus"}`} /> {hasStarted ? "Edit declaration" : "Declare investments"}
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-icon si-primary"><i className="ti ti-calendar" /></div>
          <div className="stat-label">Financial Year</div>
          <div className="stat-value">{mine?.financial_year ?? "—"}</div>
          <div className="stat-sub">
            {fyConfig ? fyCaption(fyConfig.financial_year_start_month, mine?.financial_year_start ?? 0) : ""}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-info"><i className="ti ti-adjustments-horizontal" /></div>
          <div className="stat-label">Current Regime</div>
          <div className="stat-value">{mine ? (mine.tax_regime === "new" ? "New" : "Old") : "—"}</div>
          <div className="stat-sub">changes require payroll approval</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-warn"><i className="ti ti-receipt-tax" /></div>
          <div className="stat-label">YTD TDS</div>
          <div className="stat-value">{ytdTds !== null ? formatInr(Math.round(ytdTds)) : "—"}</div>
          <div className="stat-sub">Sum of income tax deducted this financial year&apos;s payslips</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-error"><i className="ti ti-calendar-due" /></div>
          <div className="stat-label">Proof Window</div>
          <div className="stat-value">—</div>
          <div className="stat-sub">No submission deadline is configured</div>
        </div>
      </div>

      <TaxDeclarationSummary declaration={mine ?? null} isLoading={loading} />

      <TaxProofsCard declaration={mine ?? null} />

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <div className="card-title"><i className="ti ti-folder" /> Tax documents</div>
        </div>
        <p style={{ margin: "0 24px 8px", fontSize: 12, color: "var(--on-variant)" }}>
          Available statements and proof uploads.
        </p>
        <div style={{ padding: "4px 24px 8px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid var(--outline-v)", gap: 12 }}>
            <div>
              <div style={{ fontWeight: 600 }}>Form 16 · FY {mine?.financial_year ?? "—"}</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)" }}>Annual tax certificate · PDF</div>
            </div>
            <button
              className="btn btn-ghost btn-sm"
              disabled
              style={{ opacity: 0.5, cursor: "not-allowed" }}
              title="Form 16 generation is not available in this system yet"
            >
              <i className="ti ti-download" /> Download
            </button>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", gap: 12 }}>
            <div>
              <div style={{ fontWeight: 600 }}>Other tax documents</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)" }}>Upload anything else under Documents → Tax proof.</div>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={onNavigateToDocuments}>
              <i className="ti ti-chevron-right" />
            </button>
          </div>
        </div>
      </div>

      {canApprove && <TaxHrQueue />}

      {showNewDeclaration && (
        <TaxDeclarationModal
          current={mine ?? null}
          onClose={() => setShowNewDeclaration(false)}
          onSaved={() => { setShowNewDeclaration(false); refetch(); }}
        />
      )}
    </div>
  );
}
