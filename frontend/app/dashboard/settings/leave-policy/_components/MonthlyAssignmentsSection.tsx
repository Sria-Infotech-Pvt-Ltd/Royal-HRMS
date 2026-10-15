"use client";

// Monthly Leave Assignments — the current monthly credits for a month, read
// from the leave-credit ledger, with an Edit dialog that saves through the
// same endpoint (and set_monthly_credit rule) as manual entry: only the
// difference from the current value is applied to the employee's balance.

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import {
  MONTHS, creditYears, describeChange, validateMonthlyCredit,
  type MonthlyAssignment, type MonthlyAssignmentsResponse,
} from "@/lib/monthlyLeave";

function apiMessage(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function EditAssignmentModal({ row, onClose, onSaved }: {
  row: MonthlyAssignment; onClose: () => void; onSaved: (message: string) => void;
}) {
  const [credit, setCredit] = useState(String(row.credit));
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const validation = validateMonthlyCredit(credit);
  const next = validation ? null : Number(credit);
  const unchanged = next === row.credit;

  async function save() {
    if (next === null || unchanged) return;
    setSaving(true);
    setErrorMsg(null);
    try {
      const { data } = await clientApi.post(API.leave.monthlyCredits, {
        employee_id: row.employee_id, leave_type: row.leave_type, year: row.year, month: row.month, credit: credit.trim(),
      });
      onSaved(data.message);
    } catch (err) {
      setErrorMsg(apiMessage(err, "Could not save the monthly credit."));
      setConfirming(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-edit" style={{ marginRight: 8 }} />Edit monthly leave credit</>}
      onClose={onClose}
      closeDisabled={saving}
      footer={
        <>
          <button className="btn btn-ghost" onClick={confirming ? () => setConfirming(false) : onClose} disabled={saving}>
            {confirming ? "Back" : "Cancel"}
          </button>
          {confirming ? (
            <button className="btn btn-filled" onClick={save} disabled={saving}>
              {saving ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</> : <><i className="ti ti-check" /> Confirm</>}
            </button>
          ) : (
            <button className="btn btn-filled" onClick={() => setConfirming(true)} disabled={!!validation || unchanged}>
              Review change
            </button>
          )}
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 14, fontSize: 13 }}>
        <div style={{ lineHeight: 1.7 }}>
          <div><strong>{row.employee_name}</strong> · {row.employee_id}{row.branch ? ` · ${row.branch}` : ""}</div>
          <div>{row.leave_type_label} · {MONTHS[row.month - 1]} {row.year}</div>
          <div>Current monthly credit: <strong>{row.credit} day(s)</strong></div>
        </div>

        {errorMsg && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{errorMsg}</div></div>}

        {!confirming ? (
          <div className="field-group" style={{ maxWidth: 220 }}>
            <label className="field-label">New monthly leave credit (days)</label>
            <input className={`field-input${validation ? " field-error" : ""}`} inputMode="decimal" autoFocus
              value={credit} onChange={e => { setCredit(e.target.value); setErrorMsg(null); }} />
            {validation
              ? <div className="field-error-msg">{validation}</div>
              : <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>0–31, one decimal place. 0 removes this month&apos;s credit.</div>}
          </div>
        ) : (
          <div className="alert alert-info">
            <i className="ti ti-info-circle" />
            <div>
              <div>Previous: <strong>{row.credit}</strong> day(s) → New: <strong>{next}</strong> day(s)</div>
              <div style={{ marginTop: 4 }}>{describeChange(row.credit, next ?? 0)}</div>
              <div style={{ marginTop: 4, fontSize: 12 }}>
                The change is recorded in the employee&apos;s leave credit history. A reduction is refused if it would
                leave less than their used plus pending leave.
              </div>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

export default function MonthlyAssignmentsSection({ refreshKey, onChanged }: {
  refreshKey: number; onChanged: () => void;
}) {
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [data, setData] = useState<MonthlyAssignmentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [editing, setEditing] = useState<MonthlyAssignment | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErrorMsg(null);
    clientApi
      .get(API.leave.monthlyAssignments, { params: { year, month } })
      .then(({ data }) => { if (!cancelled) setData(data.data); })
      .catch(err => { if (!cancelled) { setData(null); setErrorMsg(apiMessage(err, "Could not load monthly leave assignments.")); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [year, month, refreshKey]);

  const summary = data?.summary;

  return (
    <div className="card mb-24">
      <div className="card-header" style={{ flexWrap: "wrap", gap: 12 }}>
        <div className="card-title"><i className="ti ti-list-details" /> Monthly Leave Assignments</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select className="field-input" style={{ width: "auto", padding: "6px 10px" }} value={month}
            onChange={e => { setMonth(Number(e.target.value)); setOkMsg(null); }} aria-label="Month">
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
          <select className="field-input" style={{ width: "auto", padding: "6px 10px" }} value={year}
            onChange={e => { setYear(Number(e.target.value)); setOkMsg(null); }} aria-label="Year">
            {creditYears().map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>
      <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
        {summary && (
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {[
              { label: "Employees assigned", value: summary.employees, hint: "unique employees" },
              { label: "Credit entries", value: summary.entries, hint: "employee + leave type" },
              { label: "Total days credited", value: summary.total_days, hint: `${MONTHS[month - 1]} ${year}` },
            ].map(s => (
              <div key={s.label} style={{ flex: "1 1 160px", padding: "12px 16px", border: "1px solid var(--outline-v)", borderRadius: 8, background: "var(--bg-low)" }}>
                <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{s.label}</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: "var(--on-bg)" }}>{s.value}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{s.hint}</div>
              </div>
            ))}
          </div>
        )}

        {okMsg && <div className="alert alert-success"><i className="ti ti-circle-check" /><div>{okMsg}</div></div>}
        {errorMsg && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{errorMsg}</div></div>}

        {loading ? (
          <div style={{ fontSize: 13, color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Loading assignments…
          </div>
        ) : data && data.assignments.length === 0 ? (
          <div style={{ fontSize: 13, color: "var(--on-variant)" }}>
            No monthly leave credits assigned for {MONTHS[month - 1]} {year}. Use the import or manual entry above to add them.
          </div>
        ) : data ? (
          <div style={{ overflowX: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
            <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
              <thead>
                <tr>
                  <th>Employee Code</th><th>Employee Name</th><th>Branch</th><th>Leave Type</th>
                  <th>Month</th><th>Year</th><th style={{ textAlign: "right" }}>Monthly Leave Credit (days)</th>
                  <th>Last Updated</th><th>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.assignments.map(a => (
                  <tr key={`${a.employee_id}-${a.leave_type}`}>
                    <td>{a.employee_id}</td>
                    <td>{a.employee_name}{!a.is_active && <span style={{ color: "var(--on-variant)" }}> (inactive)</span>}</td>
                    <td>{a.branch || "—"}</td>
                    <td>{a.leave_type_label}</td>
                    <td>{MONTHS[a.month - 1]}</td>
                    <td>{a.year}</td>
                    <td style={{ textAlign: "right", fontWeight: 600 }}>{a.credit}</td>
                    <td>{formatWhen(a.last_updated)}</td>
                    <td>
                      {a.is_active ? (
                        <button className="btn btn-ghost btn-sm" onClick={() => { setEditing(a); setOkMsg(null); }}>
                          <i className="ti ti-pencil" /> Edit
                        </button>
                      ) : <span style={{ fontSize: 12, color: "var(--on-variant)" }}>—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      {editing && (
        <EditAssignmentModal
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={message => { setEditing(null); setOkMsg(message); onChanged(); }}
        />
      )}
    </div>
  );
}
