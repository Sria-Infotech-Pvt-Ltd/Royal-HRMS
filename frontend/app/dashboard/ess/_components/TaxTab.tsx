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
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import ConfirmModal from "@/components/ConfirmModal";
import TaxDeclarationModal from "./TaxDeclarationModal";
import type { PagedResponse } from "@/app/dashboard/my-payslip/_components/types";
import { currentFinancialYearStart } from "@/app/dashboard/my-payslip/_components/types";

interface PayslipTdsRow {
  cycle_start: string;
  income_tax: string;
}

export interface ApiTaxDeclaration {
  id: string;
  employee_name: string;
  financial_year_start: number;
  financial_year: string;
  tax_regime: "old" | "new";
  tax_regime_display: string;
  declared_investments: Record<string, number>;
  status: "draft" | "submitted" | "approved";
  status_display: string;
  submitted_at: string | null;
  approved_at: string | null;
  approved_by_name: string;
}

interface FinancialYearConfig {
  financial_year_start_month: string;
  current_financial_year: string;
}

export const SECTIONS = [
  { key: "80C",     label: "Section 80C (PF, ELSS, life insurance, etc.)" },
  { key: "80D",     label: "Section 80D (health insurance premium)" },
  { key: "80CCD1B", label: "Section 80CCD(1B) (NPS)" },
  { key: "HRA",     label: "HRA exemption (rent receipts)" },
];

const STATUS_BADGE: Record<string, string> = {
  draft: "badge-neutral", submitted: "badge-warn", approved: "badge-success",
};

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

function sectionsSummary(investments: Record<string, number>): string {
  const parts = SECTIONS
    .map(s => ({ key: s.key, amount: investments[s.key] ?? 0 }))
    .filter(p => p.amount > 0)
    .map(p => `${p.key} ${formatInr(p.amount)}`);
  return parts.length > 0 ? parts.join(" · ") : "No investments declared yet";
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
  const hasSubmitted = !!mine && mine.status !== "draft";

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
            <i className="ti ti-plus" /> New declaration
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

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <div className="card-title"><i className="ti ti-file-invoice" /> My declarations</div>
        </div>
        <p style={{ margin: "0 24px 8px", fontSize: 12, color: "var(--on-variant)" }}>
          Submitted items are reviewed by Payroll Operations.
        </p>
        {loading ? (
          <div className="empty-state">
            <i className="ti ti-loader-2 spin" />
            <h3>Loading declaration…</h3>
          </div>
        ) : !hasSubmitted ? (
          <div className="empty-state">
            <i className="ti ti-file-invoice" />
            <h3>No declarations submitted</h3>
            <p>Start a declaration to see its approval status here.</p>
          </div>
        ) : (
          <div style={{ padding: "4px 24px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0" }}>
              <div>
                <div style={{ fontWeight: 600 }}>Tax declaration — FY {mine!.financial_year}</div>
                <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
                  {mine!.tax_regime_display} · {sectionsSummary(mine!.declared_investments)}
                </div>
              </div>
              <span className={`badge ${STATUS_BADGE[mine!.status]}`}>{mine!.status_display}</span>
            </div>
          </div>
        )}
      </div>

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
              <div style={{ fontWeight: 600 }}>Upload investment proof</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)" }}>Select Tax proof in Documents.</div>
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
          onSubmitted={() => { setShowNewDeclaration(false); refetch(); }}
        />
      )}
    </div>
  );
}

function TaxHrQueue() {
  const { data: all, loading, error, refetch } = useFetch<ApiTaxDeclaration[]>(API.payroll.taxDeclarations);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [approveErr, setApproveErr] = useState<string | null>(null);
  const [confirmTarget, setConfirmTarget] = useState<ApiTaxDeclaration | null>(null);

  async function approve(id: string) {
    setConfirmTarget(null);
    setBusyId(id);
    setApproveErr(null);
    try {
      await clientApi.post(API.payroll.approveTaxDeclaration(id));
      refetch();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "Failed to approve this declaration. Please try again.";
      setApproveErr(msg);
    } finally {
      setBusyId(null);
    }
  }

  const list = all ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-list-details" /> HR review queue</div>
      </div>
      {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}
      {approveErr && (
        <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>
          <i className="ti ti-alert-circle" /> {approveErr}
        </div>
      )}
      {loading ? (
        <div className="empty-state">
          <i className="ti ti-loader-2 spin" />
          <h3>Loading…</h3>
        </div>
      ) : list.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-file-invoice" />
          <h3>No declarations yet</h3>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>Regime</th>
                <th>Status</th>
                <th>Submitted</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {list.map(d => (
                <tr key={d.id}>
                  <td style={{ fontWeight: 600 }}>{d.employee_name}</td>
                  <td>{d.tax_regime_display}</td>
                  <td><span className={`badge ${STATUS_BADGE[d.status]}`}>{d.status_display}</span></td>
                  <td style={{ color: "var(--on-variant)" }}>{d.submitted_at ? formatDate(d.submitted_at) : "—"}</td>
                  <td>
                    {d.status === "submitted" && (
                      <button className="btn btn-filled btn-sm" onClick={() => setConfirmTarget(d)} disabled={busyId === d.id}>
                        {busyId === d.id ? "Approving…" : "Approve"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {confirmTarget && (
        <ConfirmModal
          title="Approve this tax declaration?"
          body={`This locks ${confirmTarget.employee_name}'s FY ${confirmTarget.financial_year} declaration (${confirmTarget.tax_regime_display}, ${sectionsSummary(confirmTarget.declared_investments)}) — they will no longer be able to change their regime or declared investments for this financial year.`}
          confirmLabel="Approve"
          saving={busyId === confirmTarget.id}
          onConfirm={() => approve(confirmTarget.id)}
          onCancel={() => setConfirmTarget(null)}
        />
      )}
    </div>
  );
}
