"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";

interface LeavePolicy {
  id: number;
  leave_type: string;
  leave_type_display: string;
  annual_days: number;
  can_carry_forward: boolean;
  max_carry_forward_days: number;
  policy_note: string;
  is_active: boolean;
  updated_at: string;
}

interface EditForm {
  annual_days: number;
  can_carry_forward: boolean;
  max_carry_forward_days: number;
  policy_note: string;
  is_active: boolean;
}

const TYPE_COLORS: Record<string, string> = {
  casual:    "#1e4e8c",
  earned:    "#1b8a6b",
  sick:      "#b5651d",
  lwp:       "#6b7280",
  maternity: "#ad95cf",
  paternity: "#0e7c86",
};

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function PolicyTab() {
  const { data: policies, loading, error, refetch } = useFetch<LeavePolicy[]>(API.leave.policy);

  const [editing,   setEditing]   = useState<LeavePolicy | null>(null);
  const [form,      setForm]      = useState<EditForm>({ annual_days: 0, can_carry_forward: false, max_carry_forward_days: 0, policy_note: "", is_active: true });
  const [errors,    setErrors]    = useState<Record<string, string>>({});
  const [saving,    setSaving]    = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  function openEdit(p: LeavePolicy) {
    setEditing(p);
    setForm({ annual_days: Number(p.annual_days), can_carry_forward: p.can_carry_forward, max_carry_forward_days: p.max_carry_forward_days, policy_note: p.policy_note, is_active: p.is_active });
    setErrors({});
    setSaveError(null);
  }

  function closeModal() { setEditing(null); }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (form.annual_days < 0) e.annual_days = "Annual days cannot be negative.";
    if (form.can_carry_forward && form.max_carry_forward_days < 1) e.max_carry_forward_days = "Must be at least 1 when carry forward is enabled.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function save() {
    if (!editing || !validate()) return;
    setSaving(true);
    setSaveError(null);
    try {
      await clientApi.put(API.leave.policyDetail(editing.leave_type), form);
      refetch();
      closeModal();
    } catch (err: unknown) {
      setSaveError((err as { message?: string })?.message ?? "Failed to save policy.");
    } finally {
      setSaving(false);
    }
  }

  function field(key: keyof EditForm, value: string | number | boolean) {
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });
    setForm(prev => ({ ...prev, [key]: value }));
  }

  const list = policies ?? [];

  return (
    <>
      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 1, background: "var(--outline-v)", borderRadius: "var(--radius-lg)", overflow: "hidden", marginBottom: 24 }}>
        {[
          { icon: "ti-beach",        color: "var(--primary)", bg: "rgba(30,78,140,0.08)",  label: "Total Types",   value: list.length },
          { icon: "ti-circle-check", color: "var(--success)", bg: "rgba(27,138,107,0.08)", label: "Active",        value: list.filter(t => t.is_active).length },
          { icon: "ti-repeat",       color: "var(--warn)",    bg: "rgba(181,101,29,0.08)", label: "Carry Forward", value: list.filter(t => t.can_carry_forward).length },
        ].map((s, i) => (
          <div key={i} style={{ background: "var(--surface)", padding: "18px 22px", display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ width: 42, height: 42, borderRadius: 11, background: s.bg, display: "flex", alignItems: "center", justifyContent: "center", color: s.color, flexShrink: 0 }}>
              <i className={`ti ${s.icon}`} style={{ fontSize: 20 }} />
            </div>
            <div>
              <div style={{ fontSize: 24, fontWeight: 700, color: "var(--on-bg)", lineHeight: 1 }}>{s.value}</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-beach" /> Leave Types</div>
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{list.length} configured</span>
        </div>

        {loading && <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--on-variant)" }}><Spin /> &nbsp;Loading policies…</div>}
        {error   && <div style={{ padding: "24px", color: "var(--error)", fontSize: 14 }}>{error}</div>}

        {!loading && !error && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th style={{ textAlign: "center" }}>Annual Days</th>
                  <th style={{ textAlign: "center" }}>Carry Fwd</th>
                  <th style={{ textAlign: "center" }}>Max Carry Fwd</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th>Policy Note</th>
                  <th style={{ textAlign: "center" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.map(p => (
                  <tr key={p.leave_type}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{ width: 10, height: 10, borderRadius: "50%", background: TYPE_COLORS[p.leave_type] ?? "#6b7280", flexShrink: 0 }} />
                        <span style={{ fontWeight: 600, fontSize: 13 }}>{p.leave_type_display}</span>
                      </div>
                    </td>
                    <td style={{ textAlign: "center", fontWeight: 700, fontSize: 15, color: "var(--primary)" }}>{Number(p.annual_days)}</td>
                    <td style={{ textAlign: "center" }}>
                      {p.can_carry_forward ? <span className="badge badge-info">Yes</span> : <span className="badge badge-neutral">No</span>}
                    </td>
                    <td style={{ textAlign: "center", fontWeight: 600 }}>
                      {p.can_carry_forward ? `${p.max_carry_forward_days}d` : <span style={{ color: "var(--outline)" }}>—</span>}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`badge ${p.is_active ? "badge-success" : "badge-neutral"}`}>
                        {p.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: "var(--on-variant)", maxWidth: 220 }}>
                      {p.policy_note || <span style={{ color: "var(--outline)" }}>—</span>}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <button className="btn btn-ghost" style={{ width: 28, height: 28, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6 }} onClick={() => openEdit(p)}>
                        <i className="ti ti-edit" style={{ fontSize: 13 }} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editing && (
        <div className="modal-overlay open">
          <div className="modal" style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <div className="modal-title"><i className="ti ti-beach" style={{ marginRight: 8 }} />Edit: {editing.leave_type_display}</div>
              <button className="modal-close" onClick={closeModal}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              {saveError && (
                <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>{saveError}</div>
              )}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
                <div className="field-group mb-16">
                  <label className="field-label">Annual Days *</label>
                  <input className={`field-input${errors.annual_days ? " field-error" : ""}`} type="number" min={0} step={0.5} value={form.annual_days} onChange={e => field("annual_days", Number(e.target.value))} />
                  {errors.annual_days && <p className="field-error-msg">{errors.annual_days}</p>}
                </div>
                <div className="field-group mb-16">
                  <label className="field-label">Max Carry Fwd (days)</label>
                  <input className={`field-input${errors.max_carry_forward_days ? " field-error" : ""}`} type="number" min={0} value={form.max_carry_forward_days} onChange={e => field("max_carry_forward_days", Number(e.target.value))} disabled={!form.can_carry_forward} />
                  {errors.max_carry_forward_days && <p className="field-error-msg">{errors.max_carry_forward_days}</p>}
                </div>
              </div>
              <div className="field-group mb-16">
                <label className="field-label">Policy Note</label>
                <textarea className="field-input" rows={3} value={form.policy_note} onChange={e => field("policy_note", e.target.value)} placeholder="Visible to employees when applying for leave" style={{ resize: "none" }} />
              </div>
              <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 4 }}>
                <label className="module-check">
                  <input type="checkbox" checked={form.can_carry_forward} onChange={e => field("can_carry_forward", e.target.checked)} />
                  <span>Allow Carry Forward</span>
                </label>
                <label className="module-check">
                  <input type="checkbox" checked={form.is_active} onChange={e => field("is_active", e.target.checked)} />
                  <span>Active</span>
                </label>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={closeModal}>Cancel</button>
              <button className="btn btn-filled" onClick={save} disabled={saving}>
                {saving ? <><Spin />&nbsp;Saving…</> : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
