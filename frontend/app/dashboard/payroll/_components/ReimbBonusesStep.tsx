"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { EmployeePayslip } from "@/types/payroll";

interface Props {
  cycleId: string;
  enableReimbursements: boolean;
  enableBonuses: boolean;
  onNext: () => void;
  onBack: () => void;
}

interface PagedResponse<T> { results: T[]; count: number; }

const fmt = (n: number | string) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

interface EditState {
  payslip: EmployeePayslip;
  reimbursements: string;
  bonus: string;
}

export default function ReimbBonusesStep({
  cycleId, enableReimbursements, enableBonuses, onNext, onBack,
}: Props) {
  const { data: payslipPage, loading, refetch } =
    useFetch<PagedResponse<EmployeePayslip>>(API.payroll.cyclePayslips(cycleId));

  const [editState, setEditState] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const payslips = payslipPage?.results ?? [];

  function flash(text: string) {
    setMsg(text);
    setTimeout(() => setMsg(null), 3000);
  }

  async function saveEdit() {
    if (!editState) return;
    setSaving(true);
    try {
      await clientApi.put(API.payroll.payslipReimbBonus(editState.payslip.id), {
        reimbursements: editState.reimbursements,
        bonus: editState.bonus,
      });
      setEditState(null);
      refetch();
      flash("Saved.");
    } catch {
      flash("Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  const totalReimb = payslips.reduce((s, p) => s + Number(p.reimbursements), 0);
  const totalBonus = payslips.reduce((s, p) => s + Number(p.bonus), 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {msg && (
        <div className={`alert ${msg === "Saved." ? "alert-success" : "alert-error"}`}>
          <i className={`ti ${msg === "Saved." ? "ti-circle-check" : "ti-alert-circle"}`} />
          {msg}
        </div>
      )}

      {enableReimbursements && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-receipt" /> Reimbursements</div>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Total: <strong style={{ color: "var(--info)" }}>{fmt(totalReimb)}</strong>
            </span>
          </div>
          {loading ? (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 20 }} />
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th style={{ textAlign: "right" }}>Reimbursements (₹)</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {payslips.map(p => (
                    <tr key={p.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--info)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700 }}>
                            {p.employee_name.charAt(0)}
                          </div>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: 13 }}>{p.employee_name}</div>
                            <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.department}</div>
                          </div>
                        </div>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 600, color: Number(p.reimbursements) > 0 ? "var(--info)" : "var(--outline)" }}>
                        {Number(p.reimbursements) > 0 ? fmt(p.reimbursements) : "—"}
                      </td>
                      <td>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => setEditState({ payslip: p, reimbursements: p.reimbursements, bonus: p.bonus })}
                        >
                          <i className="ti ti-edit" /> Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                  <tr style={{ background: "var(--bg-low)" }}>
                    <td style={{ fontWeight: 700 }}>Total</td>
                    <td style={{ textAlign: "right", fontWeight: 700, color: "var(--info)" }}>{fmt(totalReimb)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {enableBonuses && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-gift" /> Bonuses</div>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Total: <strong style={{ color: "var(--warn)" }}>{fmt(totalBonus)}</strong>
            </span>
          </div>
          {loading ? (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 20 }} />
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th style={{ textAlign: "right" }}>Bonus (₹)</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {payslips.map(p => (
                    <tr key={p.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--warn)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700 }}>
                            {p.employee_name.charAt(0)}
                          </div>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: 13 }}>{p.employee_name}</div>
                            <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.department}</div>
                          </div>
                        </div>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 600, color: Number(p.bonus) > 0 ? "var(--warn)" : "var(--outline)" }}>
                        {Number(p.bonus) > 0 ? fmt(p.bonus) : "—"}
                      </td>
                      <td>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => setEditState({ payslip: p, reimbursements: p.reimbursements, bonus: p.bonus })}
                        >
                          <i className="ti ti-edit" /> Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                  <tr style={{ background: "var(--bg-low)" }}>
                    <td style={{ fontWeight: 700 }}>Total</td>
                    <td style={{ textAlign: "right", fontWeight: 700, color: "var(--warn)" }}>{fmt(totalBonus)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
        <button className="btn btn-filled" onClick={onNext}>Continue <i className="ti ti-arrow-right" /></button>
      </div>

      {/* Edit modal */}
      {editState && (
        <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && setEditState(null)}>
          <div className="modal" style={{ maxWidth: 420 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">Edit — {editState.payslip.employee_name}</div>
              <button className="modal-close" onClick={() => setEditState(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {enableReimbursements && (
                <div className="field-group">
                  <label className="field-label">Reimbursements (₹)</label>
                  <input
                    type="number"
                    className="field-input"
                    min={0}
                    step={100}
                    value={editState.reimbursements}
                    onChange={e => setEditState(s => s ? { ...s, reimbursements: e.target.value } : s)}
                  />
                </div>
              )}
              {enableBonuses && (
                <div className="field-group">
                  <label className="field-label">Bonus (₹)</label>
                  <input
                    type="number"
                    className="field-input"
                    min={0}
                    step={500}
                    value={editState.bonus}
                    onChange={e => setEditState(s => s ? { ...s, bonus: e.target.value } : s)}
                  />
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setEditState(null)}>Cancel</button>
              <button className="btn btn-filled" onClick={saveEdit} disabled={saving}>
                {saving ? <><i className="ti ti-loader-2 animate-spin" /> Saving…</> : <><i className="ti ti-check" /> Save</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
