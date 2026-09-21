"use client";

// Tax declaration — self-service regime choice + declared investment
// amounts, submitted for HR review. Deliberately does NOT compute actual
// income tax or show a YTD TDS figure — no such computation exists anywhere
// in this codebase (confirmed before building this), and fabricating one
// would be worse than not showing it. This only records what the employee
// declared and its HR-review status.

import { useState, useEffect } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";

interface ApiTaxDeclaration {
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

const SECTIONS = [
  { key: "80C",     label: "Section 80C (PF, ELSS, life insurance, etc.)" },
  { key: "80D",     label: "Section 80D (health insurance premium)" },
  { key: "80CCD1B", label: "Section 80CCD(1B) (NPS)" },
  { key: "HRA",     label: "HRA exemption (rent receipts)" },
];

const STATUS_BADGE: Record<string, string> = {
  draft: "badge-neutral", submitted: "badge-warn", approved: "badge-success",
};

export default function TaxTab() {
  const canApprove = usePermission("tax_declarations.approve");
  const { data: mine, loading, error, refetch } = useFetch<ApiTaxDeclaration>(API.payroll.myTaxDeclaration);

  const [regime, setRegime] = useState<"old" | "new">("new");
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  useEffect(() => {
    if (!mine) return;
    setRegime(mine.tax_regime);
    setAmounts(Object.fromEntries(SECTIONS.map(s => [s.key, String(mine.declared_investments[s.key] ?? "")])));
  }, [mine]);

  const isLocked = mine?.status === "approved";

  async function handleSave() {
    setSaveErr(null);
    setSaveMsg(null);
    setSaving(true);
    try {
      const declared_investments = Object.fromEntries(
        Object.entries(amounts).filter(([, v]) => v.trim() !== "").map(([k, v]) => [k, Number(v)]),
      );
      await clientApi.patch(API.payroll.myTaxDeclaration, { tax_regime: regime, declared_investments });
      setSaveMsg("Saved.");
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveErr(msg ?? "Failed to save declaration.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmit() {
    setSaveErr(null);
    setSaveMsg(null);
    setSubmitting(true);
    try {
      await handleSave();
      await clientApi.post(API.payroll.submitTaxDeclaration);
      setSaveMsg("Submitted for HR review.");
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveErr(msg ?? "Failed to submit declaration.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <div className="card-title"><i className="ti ti-file-invoice" /> My tax declaration {mine ? `— FY ${mine.financial_year}` : ""}</div>
          {mine && <span className={`badge ${STATUS_BADGE[mine.status]}`}>{mine.status_display}</span>}
        </div>

        {loading ? (
          <div className="empty-state">
            <i className="ti ti-loader-2 spin" />
            <h3>Loading declaration…</h3>
          </div>
        ) : (
          <div style={{ padding: "20px 24px" }}>
            {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}
            {saveErr && <div className="alert alert-error" style={{ marginBottom: 16 }}>{saveErr}</div>}
            {saveMsg && <div className="alert alert-success" style={{ marginBottom: 16 }}>{saveMsg}</div>}
            {isLocked && (
              <div className="alert alert-info" style={{ marginBottom: 16 }}>
                This declaration has been approved by HR and can no longer be edited.
              </div>
            )}

            <div className="field-group" style={{ marginBottom: 16, maxWidth: 320 }}>
              <label className="field-label">Tax Regime</label>
              <select
                className="field-input field-select"
                value={regime}
                disabled={isLocked}
                onChange={e => setRegime(e.target.value as "old" | "new")}
              >
                <option value="new">New Regime (115BAC)</option>
                <option value="old">Old Regime</option>
              </select>
              <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
                Elect once per financial year. Changes follow HR review.
              </p>
            </div>

            <h4 style={{ fontSize: "0.9rem", marginBottom: 10 }}>Declared investments</h4>
            <div className="form-row cols-2" style={{ marginBottom: 16 }}>
              {SECTIONS.map(s => (
                <div className="field-group" key={s.key}>
                  <label className="field-label">{s.label}</label>
                  <input
                    className="field-input"
                    type="number"
                    min={0}
                    disabled={isLocked}
                    value={amounts[s.key] ?? ""}
                    onChange={e => setAmounts(prev => ({ ...prev, [s.key]: e.target.value }))}
                    placeholder="0"
                  />
                </div>
              ))}
            </div>

            {!isLocked && (
              <div style={{ display: "flex", gap: 10 }}>
                <button className="btn btn-ghost" onClick={handleSave} disabled={saving || submitting}>
                  {saving ? "Saving…" : "Save draft"}
                </button>
                <button className="btn btn-filled" onClick={handleSubmit} disabled={saving || submitting}>
                  {submitting ? "Submitting…" : "Submit for HR review"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {canApprove && <TaxHrQueue />}
    </div>
  );
}

function TaxHrQueue() {
  const { data: all, loading, error, refetch } = useFetch<ApiTaxDeclaration[]>(API.payroll.taxDeclarations);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function approve(id: string) {
    setBusyId(id);
    try {
      await clientApi.post(API.payroll.approveTaxDeclaration(id));
      refetch();
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
                      <button className="btn btn-filled btn-sm" onClick={() => approve(d.id)} disabled={busyId === d.id}>
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
    </div>
  );
}
