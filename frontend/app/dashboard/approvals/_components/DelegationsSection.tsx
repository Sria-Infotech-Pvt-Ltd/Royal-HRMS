"use client";

// Approvals → Delegation: hand my leave / attendance approvals to a colleague
// for a period (e.g. while I'm on leave). The delegate can act on requests
// waiting for me at either stage; every create / revoke is audited.

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import {
  DELEGATION_STATE_BADGE, DELEGATION_STATE_LABEL, WORKFLOW_LABEL, apiMessage, delegationState, localToday,
  validateDelegation, type Delegation, type DelegationForm, type PersonRef, type Workflow,
} from "@/lib/approvalWorkflows";

const EMPTY: DelegationForm = { delegate: "", start_date: "", end_date: "", workflows: ["leave"], reason: "" };

export default function DelegationsSection() {
  const today = localToday();
  const { data: rows, loading, error, refetch } = useFetch<Delegation[]>(API.approvals.delegations);
  const [form, setForm] = useState<DelegationForm>({ ...EMPTY, start_date: today });
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState("");
  const [notice, setNotice] = useState("");

  const primary: Workflow = form.workflows[0] ?? "leave";
  const { data: eligible } = useFetch<PersonRef[]>(`${API.approvals.delegationsEligible}?workflow=${primary}`);

  const errors = validateDelegation(form, today);

  const given = (rows ?? []).filter(d => d.given);
  const received = (rows ?? []).filter(d => d.received);

  function toggleWorkflow(w: Workflow, on: boolean) {
    setForm(f => ({ ...f, workflows: on ? [...new Set([...f.workflows, w])] : f.workflows.filter(x => x !== w) }));
  }

  async function create() {
    setTouched(true);
    if (Object.keys(errors).length) return;
    setSaving(true);
    setApiError("");
    setNotice("");
    try {
      await clientApi.post(API.approvals.delegations, form);
      setForm({ ...EMPTY, start_date: today });
      setTouched(false);
      setNotice("Delegation created. The delegate has been notified.");
      refetch();
    } catch (err) {
      setApiError(apiMessage(err, "Failed to create the delegation."));
    } finally {
      setSaving(false);
    }
  }

  async function revoke(d: Delegation) {
    if (!window.confirm(`Revoke the delegation to ${d.delegate.name}?`)) return;
    setApiError("");
    try {
      await clientApi.post(API.approvals.delegationRevoke(d.id));
      setNotice("Delegation revoked.");
      refetch();
    } catch (err) {
      setApiError(apiMessage(err, "Failed to revoke the delegation."));
    }
  }

  const show = (k: string) => touched && errors[k]
    ? <div className="text-[12px] text-red-600 mt-1" role="alert">{errors[k]}</div> : null;

  const table = (list: Delegation[], who: "delegate" | "delegator", empty: string) => (
    list.length === 0 ? <div className="text-[13px] text-[var(--on-variant)] py-3">{empty}</div> : (
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--outline-v)", textAlign: "left", color: "var(--on-variant)" }}>
              <th style={{ padding: 8 }}>{who === "delegate" ? "Delegate" : "On behalf of"}</th>
              <th style={{ padding: 8 }}>Period</th>
              <th style={{ padding: 8 }}>Requests</th>
              <th style={{ padding: 8 }}>Status</th>
              <th style={{ padding: 8 }} />
            </tr>
          </thead>
          <tbody>
            {list.map(d => {
              const st = delegationState(d, today);
              return (
                <tr key={d.id} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                  <td style={{ padding: 8 }}>
                    {d[who].name}
                    {d.reason && <div className="text-[11px] text-[var(--on-variant)]">{d.reason}</div>}
                  </td>
                  <td style={{ padding: 8, whiteSpace: "nowrap" }}>{d.start_date} → {d.end_date}</td>
                  <td style={{ padding: 8 }}>{d.workflows.map(w => WORKFLOW_LABEL[w]).join(", ")}</td>
                  <td style={{ padding: 8 }}><span className={`badge ${DELEGATION_STATE_BADGE[st]}`}>{DELEGATION_STATE_LABEL[st]}</span></td>
                  <td style={{ padding: 8, textAlign: "right" }}>
                    {d.can_revoke && (
                      <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => revoke(d)}>
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    )
  );

  return (
    <div className="settings-card" data-testid="delegations-section">
      <div style={{ fontWeight: 600, fontSize: 15 }}>Delegate my approvals</div>
      <div className="text-[12px] text-[var(--on-variant)] mt-1 mb-3">
        While you are away, a colleague in your branch who can approve the same requests acts on requests waiting for you.
        You keep your own access. Up to 180 days; one delegation per period.
      </div>

      {notice && <div className="alert alert-success mb-3"><i className="ti ti-check" /> {notice}</div>}
      {apiError && <div className="alert alert-error mb-3"><i className="ti ti-alert-circle" /> {apiError}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
        <div className="field-group">
          <label className="field-label" htmlFor="dlg-delegate">Delegate *</label>
          <select id="dlg-delegate" className="field-input field-select" value={form.delegate}
                  onChange={e => setForm(f => ({ ...f, delegate: e.target.value }))}>
            <option value="">— Select —</option>
            {(eligible ?? []).map(p => <option key={p.id} value={p.id}>{p.name}{p.employee_id ? ` (${p.employee_id})` : ""}</option>)}
          </select>
          {show("delegate")}
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="dlg-start">From *</label>
          <input id="dlg-start" type="date" className="field-input" value={form.start_date} min={today}
                 onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
          {show("start_date")}
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="dlg-end">To *</label>
          <input id="dlg-end" type="date" className="field-input" value={form.end_date} min={form.start_date || today}
                 onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} />
          {show("end_date")}
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="dlg-reason">Reason</label>
          <input id="dlg-reason" className="field-input" value={form.reason} maxLength={300} placeholder="e.g. Annual leave"
                 onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} />
          {show("reason")}
        </div>
      </div>
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginTop: 10, fontSize: 13, flexWrap: "wrap" }}>
        {(["leave", "attendance"] as Workflow[]).map(w => (
          <label key={w} style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={form.workflows.includes(w)} onChange={e => toggleWorkflow(w, e.target.checked)} />
            {WORKFLOW_LABEL[w]} requests
          </label>
        ))}
        {show("workflows")}
        <div style={{ flex: 1 }} />
        <button className="btn btn-primary" onClick={create} disabled={saving}>
          {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Delegate"}
        </button>
      </div>

      {loading && <div className="text-[13px] text-[var(--on-variant)] mt-4">Loading delegations…</div>}
      {error && <div className="alert alert-error mt-4">{error}</div>}
      {!loading && !error && (
        <>
          <div style={{ fontWeight: 600, fontSize: 13, marginTop: 20 }}>Delegated by me</div>
          {table(given, "delegate", "You haven't delegated your approvals.")}
          <div style={{ fontWeight: 600, fontSize: 13, marginTop: 16 }}>Delegated to me</div>
          {table(received, "delegator", "No one has delegated approvals to you.")}
        </>
      )}
    </div>
  );
}
