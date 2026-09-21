"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { LEAVE_NAME_RE, sanitizeLeaveName } from "@/lib/leaveValidation";
import Modal from "@/components/Modal";

interface LeavePolicy {
  id: number;
  leave_type: string;
  leave_type_display: string;
  annual_days: number;
  accrual_frequency: "annual" | "monthly";
  can_carry_forward: boolean;
  max_carry_forward_days: number;
  policy_note: string;
  is_active: boolean;
  updated_at: string;
}

interface EditForm {
  annual_days: number;
  accrual_frequency: "annual" | "monthly";
  can_carry_forward: boolean;
  max_carry_forward_days: number;
  policy_note: string;
  is_active: boolean;
}

interface CreateForm {
  leave_type_label: string;
  annual_days: number;
  accrual_frequency: "annual" | "monthly";
  can_carry_forward: boolean;
  max_carry_forward_days: number;
  policy_note: string;
  is_active: boolean;
}

const TYPE_COLORS: Record<string, string> = {
  casual:    "#7c3aed",
  earned:    "#17905a",
  sick:      "#a2620c",
  lwp:       "#6b7280",
  maternity: "#a78bfa",
  paternity: "#2563eb",
};

// Built-in leave types can be deactivated but never deleted — mirrors the
// _BUILTIN set enforced server-side in LeavePolicyView.delete().
const BUILTIN_TYPES = new Set(["casual", "earned", "sick", "lwp", "maternity", "paternity"]);

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function PolicyTab() {
  const { data: policies, loading, error, refetch } = useFetch<LeavePolicy[]>(API.leave.policy);

  // ── Edit state ────────────────────────────────────────────────────────────
  const [editing,   setEditing]   = useState<LeavePolicy | null>(null);
  const [form,      setForm]      = useState<EditForm>({ annual_days: 0, accrual_frequency: "annual", can_carry_forward: false, max_carry_forward_days: 0, policy_note: "", is_active: true });
  const [errors,    setErrors]    = useState<Record<string, string>>({});
  const [isSaving,  setIsSaving]  = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // ── Create state ──────────────────────────────────────────────────────────
  const [isCreating,    setIsCreating]    = useState(false);
  const [createForm,    setCreateForm]    = useState<CreateForm>({ leave_type_label: "", annual_days: 0, accrual_frequency: "annual", can_carry_forward: false, max_carry_forward_days: 0, policy_note: "", is_active: true });
  const [createErrors,  setCreateErrors]  = useState<Record<string, string>>({});
  const [isSubmitting,  setIsSubmitting]  = useState(false);
  const [createError,   setCreateError]   = useState<string | null>(null);

  // ── Row action state (toggle active / delete) ─────────────────────────────
  const [busyType,  setBusyType]  = useState<string | null>(null);
  const [rowError,  setRowError]  = useState<string | null>(null);

  // ── Edit handlers ─────────────────────────────────────────────────────────
  function openEdit(p: LeavePolicy) {
    setEditing(p);
    setForm({ annual_days: Number(p.annual_days), accrual_frequency: p.accrual_frequency ?? "annual", can_carry_forward: p.can_carry_forward, max_carry_forward_days: p.max_carry_forward_days, policy_note: p.policy_note ?? "", is_active: p.is_active });
    setErrors({});
    setSaveError(null);
  }

  function closeEdit() { setEditing(null); }

  function validateEdit(): boolean {
    const e: Record<string, string> = {};
    if (form.annual_days < 0) e.annual_days = "Annual days cannot be negative.";
    if (form.can_carry_forward && form.max_carry_forward_days < 1) e.max_carry_forward_days = "Must be at least 1 when carry forward is enabled.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function saveEdit() {
    if (!editing || !validateEdit()) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      await clientApi.put(API.leave.policyDetail(editing.leave_type), form);
      refetch();
      closeEdit();
    } catch (err: unknown) {
      setSaveError((err as { message?: string })?.message ?? "Failed to save policy.");
    } finally {
      setIsSaving(false);
    }
  }

  function editField(key: keyof EditForm, value: string | number | boolean) {
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });
    setForm(prev => ({
      ...prev,
      [key]: value,
      // Disabling carry forward clears any stale days left in the field —
      // otherwise a disabled-but-nonzero value could get saved silently.
      ...(key === "can_carry_forward" && value === false ? { max_carry_forward_days: 0 } : {}),
    }));
  }

  async function toggleActive(p: LeavePolicy) {
    setBusyType(p.leave_type);
    setRowError(null);
    try {
      await clientApi.put(API.leave.policyDetail(p.leave_type), { is_active: !p.is_active });
      refetch();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to update status.");
    } finally {
      setBusyType(null);
    }
  }

  async function deletePolicy(p: LeavePolicy) {
    if (!window.confirm(`Delete "${p.leave_type_display}"? This cannot be undone.`)) return;
    setBusyType(p.leave_type);
    setRowError(null);
    try {
      await clientApi.delete(API.leave.policyDetail(p.leave_type));
      refetch();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to delete leave type.");
    } finally {
      setBusyType(null);
    }
  }

  // ── Create handlers ───────────────────────────────────────────────────────
  function openCreate() {
    setCreateForm({ leave_type_label: "", annual_days: 0, accrual_frequency: "annual", can_carry_forward: false, max_carry_forward_days: 0, policy_note: "", is_active: true });
    setCreateErrors({});
    setCreateError(null);
    setIsCreating(true);
  }

  function closeCreate() { setIsCreating(false); }

  function validateCreate(): boolean {
    const e: Record<string, string> = {};
    const label = createForm.leave_type_label.trim();
    if (!label) e.leave_type_label = "Display name is required.";
    else if (!LEAVE_NAME_RE.test(label)) e.leave_type_label = "Display name can only contain letters, spaces, and hyphens — no numbers or special characters.";
    if (createForm.annual_days < 0) e.annual_days = "Annual days cannot be negative.";
    if (createForm.can_carry_forward && createForm.max_carry_forward_days < 1) e.max_carry_forward_days = "Must be at least 1 when carry forward is enabled.";
    setCreateErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submitCreate() {
    if (!validateCreate()) return;
    setIsSubmitting(true);
    setCreateError(null);
    try {
      await clientApi.post(API.leave.policy, createForm);
      refetch();
      closeCreate();
    } catch (err: unknown) {
      setCreateError((err as { message?: string })?.message ?? "Failed to create leave type.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function createField(key: keyof CreateForm, value: string | number | boolean) {
    setCreateErrors(prev => { const n = { ...prev }; delete n[key]; return n; });
    setCreateForm(prev => ({
      ...prev,
      [key]: value,
      ...(key === "can_carry_forward" && value === false ? { max_carry_forward_days: 0 } : {}),
    }));
  }

  const list = policies ?? [];

  return (
    <>
      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 1, background: "var(--outline-v)", borderRadius: "var(--radius-lg)", overflow: "hidden", marginBottom: 24 }}>
        {[
          { icon: "ti-beach",        color: "var(--primary)", bg: "rgba(124,58,237,0.08)",  label: "Total Types",   value: list.length },
          { icon: "ti-circle-check", color: "var(--success)", bg: "rgba(23,144,90,0.08)", label: "Active",        value: list.filter(t => t.is_active).length },
          { icon: "ti-repeat",       color: "var(--warn)",    bg: "rgba(162,98,12,0.08)", label: "Carry Forward", value: list.filter(t => t.can_carry_forward).length },
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
          <button className="btn btn-filled btn-sm" onClick={openCreate}>
            <i className="ti ti-plus" /> Add Leave Type
          </button>
        </div>

        {loading && <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--on-variant)" }}><Spin /> &nbsp;Loading policies…</div>}
        {error   && <div style={{ padding: "24px", color: "var(--error)", fontSize: 14 }}>{error}</div>}
        {rowError && (
          <div style={{ margin: "0 24px 16px", padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>{rowError}</div>
        )}

        {!loading && !error && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th style={{ textAlign: "center" }}>Annual Days</th>
                  <th style={{ textAlign: "center" }}>Accrual</th>
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
                      <span className="badge badge-neutral">{p.accrual_frequency === "monthly" ? "Monthly" : "Annual"}</span>
                    </td>
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
                      <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
                        <button
                          className="btn btn-ghost"
                          style={{ width: 28, height: 28, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6 }}
                          onClick={() => openEdit(p)}
                          title="Edit"
                        >
                          <i className="ti ti-edit" style={{ fontSize: 13 }} />
                        </button>
                        <button
                          className="btn btn-ghost"
                          style={{ width: 28, height: 28, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6 }}
                          onClick={() => toggleActive(p)}
                          disabled={busyType === p.leave_type}
                          title={p.is_active ? "Deactivate" : "Activate"}
                        >
                          <i className={`ti ${p.is_active ? "ti-toggle-right" : "ti-toggle-left"}`} style={{ fontSize: 13 }} />
                        </button>
                        <button
                          className="btn btn-ghost"
                          style={{
                            width: 28, height: 28, padding: 0, justifyContent: "center",
                            border: "1px solid var(--outline-v)", borderRadius: 6,
                            color: BUILTIN_TYPES.has(p.leave_type) ? "var(--outline)" : "var(--error)",
                            cursor: BUILTIN_TYPES.has(p.leave_type) ? "not-allowed" : "pointer",
                          }}
                          onClick={() => deletePolicy(p)}
                          disabled={busyType === p.leave_type || BUILTIN_TYPES.has(p.leave_type)}
                          title={BUILTIN_TYPES.has(p.leave_type) ? "Built-in leave types cannot be deleted" : "Delete"}
                        >
                          <i className="ti ti-trash" style={{ fontSize: 13 }} />
                        </button>
                      </div>
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
        <Modal
          title={<><i className="ti ti-beach" style={{ marginRight: 8 }} />Edit: {editing.leave_type_display}</>}
          onClose={closeEdit}
          maxWidth={480}
          footer={
            <>
              <button className="btn btn-ghost" onClick={closeEdit}>Cancel</button>
              <button className="btn btn-filled" onClick={saveEdit} disabled={isSaving}>
                {isSaving ? <><Spin />&nbsp;Saving…</> : "Save Changes"}
              </button>
            </>
          }
        >
          {saveError && (
            <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>{saveError}</div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
            <div className="field-group mb-16">
              <label className="field-label">Annual Days *</label>
              <input className={`field-input${errors.annual_days ? " field-error" : ""}`} type="number" min={0} step={0.5} value={form.annual_days} onChange={e => editField("annual_days", Number(e.target.value))} />
              {errors.annual_days && <p className="field-error-msg">{errors.annual_days}</p>}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Accrual</label>
              <select className="field-input field-select" value={form.accrual_frequency} onChange={e => editField("accrual_frequency", e.target.value)}>
                <option value="annual">Annual (lump sum on Jan 1)</option>
                <option value="monthly">Monthly (1/12th each month)</option>
              </select>
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Max Carry Fwd (days)</label>
              <input className={`field-input${errors.max_carry_forward_days ? " field-error" : ""}`} type="number" min={0} value={form.max_carry_forward_days} onChange={e => editField("max_carry_forward_days", Number(e.target.value))} disabled={!form.can_carry_forward} />
              {errors.max_carry_forward_days && <p className="field-error-msg">{errors.max_carry_forward_days}</p>}
            </div>
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Policy Note</label>
            <textarea className="field-input" rows={3} value={form.policy_note} onChange={e => editField("policy_note", e.target.value)} placeholder="Visible to employees when applying for leave" style={{ resize: "none" }} />
          </div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 4 }}>
            <label className="module-check">
              <input type="checkbox" checked={form.can_carry_forward} onChange={e => editField("can_carry_forward", e.target.checked)} />
              <span>Allow Carry Forward</span>
            </label>
            <label className="module-check">
              <input type="checkbox" checked={form.is_active} onChange={e => editField("is_active", e.target.checked)} />
              <span>Active</span>
            </label>
          </div>
        </Modal>
      )}

      {/* Create Modal */}
      {isCreating && (
        <Modal
          title={<><i className="ti ti-plus" style={{ marginRight: 8 }} />Add Leave Type</>}
          onClose={closeCreate}
          maxWidth={480}
          footer={
            <>
              <button className="btn btn-ghost" onClick={closeCreate}>Cancel</button>
              <button className="btn btn-filled" onClick={submitCreate} disabled={isSubmitting}>
                {isSubmitting ? <><Spin />&nbsp;Creating…</> : "Create Leave Type"}
              </button>
            </>
          }
        >
          {createError && (
            <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>{createError}</div>
          )}
          <div className="field-group mb-16">
            <label className="field-label">Display Name *</label>
            <input
              className={`field-input${createErrors.leave_type_label ? " field-error" : ""}`}
              type="text"
              placeholder="e.g. Compensatory Off"
              value={createForm.leave_type_label}
              onChange={e => createField("leave_type_label", sanitizeLeaveName(e.target.value))}
            />
            {createErrors.leave_type_label
              ? <p className="field-error-msg">{createErrors.leave_type_label}</p>
              : createForm.leave_type_label.trim() && (
                <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
                  Key: <code>{createForm.leave_type_label.trim().toLowerCase().replace(/[\s-]+/g, "_")}</code>
                </p>
              )
            }
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
            <div className="field-group mb-16">
              <label className="field-label">Annual Days *</label>
              <input className={`field-input${createErrors.annual_days ? " field-error" : ""}`} type="number" min={0} step={0.5} value={createForm.annual_days} onChange={e => createField("annual_days", Number(e.target.value))} />
              {createErrors.annual_days && <p className="field-error-msg">{createErrors.annual_days}</p>}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Accrual</label>
              <select className="field-input field-select" value={createForm.accrual_frequency} onChange={e => createField("accrual_frequency", e.target.value)}>
                <option value="annual">Annual (lump sum on Jan 1)</option>
                <option value="monthly">Monthly (1/12th each month)</option>
              </select>
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Max Carry Fwd (days)</label>
              <input className={`field-input${createErrors.max_carry_forward_days ? " field-error" : ""}`} type="number" min={0} value={createForm.max_carry_forward_days} onChange={e => createField("max_carry_forward_days", Number(e.target.value))} disabled={!createForm.can_carry_forward} />
              {createErrors.max_carry_forward_days && <p className="field-error-msg">{createErrors.max_carry_forward_days}</p>}
            </div>
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Policy Note</label>
            <textarea className="field-input" rows={3} value={createForm.policy_note} onChange={e => createField("policy_note", e.target.value)} placeholder="Visible to employees when applying for leave" style={{ resize: "none" }} />
          </div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 4 }}>
            <label className="module-check">
              <input type="checkbox" checked={createForm.can_carry_forward} onChange={e => createField("can_carry_forward", e.target.checked)} />
              <span>Allow Carry Forward</span>
            </label>
            <label className="module-check">
              <input type="checkbox" checked={createForm.is_active} onChange={e => createField("is_active", e.target.checked)} />
              <span>Active</span>
            </label>
          </div>
        </Modal>
      )}
    </>
  );
}
