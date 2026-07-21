"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { EmployeeSalaryConfig, SalaryStructureListItem } from "@/types/payroll";

interface Props { employeeId: string; }

const INR = (n: string | number) =>
  `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

export default function SalaryTab({ employeeId }: Props) {
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [form, setForm] = useState({ annual_ctc: "", effective_from: "", salary_structure: "" });

  const { data: history, loading, refetch } = useFetch<EmployeeSalaryConfig[]>(
    employeeId ? API.payroll.employeeSalaryHistory(employeeId) : null
  );
  const { data: structures } = useFetch<SalaryStructureListItem[]>(
    showModal ? API.payroll.structures : null
  );

  const current = history?.find(h => h.is_active) ?? null;
  const hasConfig = current !== null;

  function openModal() {
    setForm({
      annual_ctc: current ? String(Math.round(Number(current.annual_ctc))) : "",
      effective_from: new Date().toISOString().split("T")[0],
      salary_structure: current?.salary_structure ?? "",
    });
    setSaveErr(null);
    setShowModal(true);
  }

  async function save() {
    if (!form.annual_ctc || !form.effective_from) {
      setSaveErr("Annual CTC and Effective From are required.");
      return;
    }
    setSaving(true);
    setSaveErr(null);
    try {
      await clientApi.post(API.payroll.employeeSalary, {
        employee: employeeId,
        annual_ctc: form.annual_ctc,
        effective_from: form.effective_from,
        salary_structure: form.salary_structure || null,
      });
      setShowModal(false);
      setSuccessMsg(hasConfig ? "CTC revised successfully." : "CTC assigned successfully.");
      refetch();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to save.";
      setSaveErr(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {successMsg && (
        <div className="alert alert-success">{successMsg}</div>
      )}

      {/* Current CTC card */}
      <div className="card">
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>Current CTC</span>
          <button className="btn btn-filled btn-sm" onClick={openModal}>
            <i className={`ti ${hasConfig ? "ti-edit" : "ti-plus"}`} />
            {hasConfig ? " Revise CTC" : " Assign CTC"}
          </button>
        </div>
        <div style={{ padding: 20 }}>
          {loading ? (
            <div className="empty-state">Loading…</div>
          ) : !current ? (
            <div className="empty-state">
              <div className="empty-state-icon">₹</div>
              <div className="empty-state-title">No CTC assigned</div>
              <div className="empty-state-desc">Click &quot;Assign CTC&quot; to set this employee&apos;s compensation.</div>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 20 }}>
              <Stat label="Annual CTC" value={INR(current.annual_ctc)} large />
              <Stat label="Monthly CTC" value={INR(current.monthly_ctc)} large />
              <Stat label="Effective From" value={fmtDate(current.effective_from)} />
              <Stat label="Salary Structure" value={current.structure_name ?? "Company Default"} />
            </div>
          )}
        </div>
      </div>

      {/* Revision history */}
      {!loading && history && history.length > 0 && (
        <div className="card">
          <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)" }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>Revision History</span>
          </div>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Effective From</th>
                  <th>Annual CTC</th>
                  <th>Monthly CTC</th>
                  <th>Structure</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map(h => (
                  <tr key={h.id}>
                    <td>{fmtDate(h.effective_from)}</td>
                    <td style={{ fontVariantNumeric: "tabular-nums" }}>{INR(h.annual_ctc)}</td>
                    <td style={{ fontVariantNumeric: "tabular-nums" }}>{INR(h.monthly_ctc)}</td>
                    <td>{h.structure_name ?? <span style={{ color: "var(--text-muted)" }}>Default</span>}</td>
                    <td>
                      {h.is_active
                        ? <span className="status-badge status-active">Active</span>
                        : <span className="status-badge status-inactive">Superseded</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Assign / Revise modal */}
      {showModal && (
        <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) setShowModal(false); }}>
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">{hasConfig ? "Revise CTC" : "Assign CTC"}</span>
              <button className="modal-close" onClick={() => setShowModal(false)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              {saveErr && (
                <div className="alert alert-error" style={{ marginBottom: "1rem" }}>{saveErr}</div>
              )}

              <div className="field-group" style={{ marginBottom: "1rem" }}>
                <label className="field-label">
                  Annual CTC (₹) <span style={{ color: "var(--error)" }}>*</span>
                </label>
                <input
                  className="field-input"
                  type="number"
                  min={0}
                  step={1000}
                  placeholder="e.g. 600000"
                  value={form.annual_ctc}
                  onChange={e => setForm(f => ({ ...f, annual_ctc: e.target.value }))}
                />
                {form.annual_ctc && (
                  <div style={{ fontSize: ".78rem", color: "var(--text-secondary)", marginTop: ".25rem" }}>
                    Monthly: {INR(Math.round(Number(form.annual_ctc) / 12))}
                  </div>
                )}
              </div>

              <div className="field-group" style={{ marginBottom: "1rem" }}>
                <label className="field-label">
                  Effective From <span style={{ color: "var(--error)" }}>*</span>
                </label>
                <input
                  className="field-input"
                  type="date"
                  value={form.effective_from}
                  onChange={e => setForm(f => ({ ...f, effective_from: e.target.value }))}
                />
              </div>

              <div className="field-group">
                <label className="field-label">
                  Salary Structure{" "}
                  <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>
                    (optional)
                  </span>
                </label>
                <select
                  className="field-input field-select"
                  value={form.salary_structure}
                  onChange={e => setForm(f => ({ ...f, salary_structure: e.target.value }))}
                >
                  <option value="">— Use company default —</option>
                  {(structures ?? []).filter(s => s.is_active).map(s => (
                    <option key={s.id} value={s.id}>
                      {s.name}{s.is_default ? " (Default)" : ""}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowModal(false)} disabled={saving}>
                Cancel
              </button>
              <button
                className="btn btn-filled"
                onClick={save}
                disabled={saving || !form.annual_ctc || !form.effective_from}
              >
                {saving
                  ? <><i className="ti ti-loader-2 spin" /> Saving…</>
                  : hasConfig ? "Revise CTC" : "Assign CTC"
                }
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, large }: { label: string; value: string; large?: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".05em", color: "var(--text-muted)" }}>
        {label}
      </div>
      <div style={{ fontSize: large ? 22 : 15, fontWeight: large ? 700 : 600, color: "var(--on-bg)", fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
    </div>
  );
}
