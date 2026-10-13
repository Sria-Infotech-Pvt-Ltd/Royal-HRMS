"use client";

// HR review queue of the Tax tab — every employee's current-FY declaration, with an
// Approve action that locks the declaration (gated by tax_declarations.approve).

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import { totalDeduction } from "@/lib/taxDeclarationForm";
import ConfirmModal from "@/components/ConfirmModal";
import type { ApiTaxDeclaration } from "@/types/taxDeclaration";

const STATUS_BADGE: Record<string, string> = {
  draft: "badge-neutral", submitted: "badge-warn", approved: "badge-success",
};

function formatInr(amount: number): string {
  return `₹${Math.round(amount).toLocaleString("en-IN")}`;
}

export default function TaxHrQueue() {
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
          body={`This locks ${confirmTarget.employee_name}'s FY ${confirmTarget.financial_year} declaration (${confirmTarget.tax_regime_display}, ${formatInr(totalDeduction(confirmTarget))} deductions after limits) — they will no longer be able to change their regime or declared investments for this financial year.`}
          confirmLabel="Approve"
          saving={busyId === confirmTarget.id}
          onConfirm={() => approve(confirmTarget.id)}
          onCancel={() => setConfirmTarget(null)}
        />
      )}
    </div>
  );
}
