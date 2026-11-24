"use client";

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { LEAVE_NAME_RE, sanitizeLeaveName } from "@/lib/leaveValidation";
import Modal from "@/components/Modal";
import { confirmDialog } from "@/components/DialogProvider";
import LeaveTypeStats from "./LeaveTypeStats";
import LeaveTypesTable from "./LeaveTypesTable";
import type { LeavePolicy } from "./leaveTypeView";

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

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function PolicyTab() {
  const t = useT();
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
    if (form.annual_days < 0) e.annual_days = t("Annual days cannot be negative.");
    if (form.can_carry_forward && form.max_carry_forward_days < 1) e.max_carry_forward_days = t("Must be at least 1 when carry forward is enabled.");
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
      setSaveError((err as { message?: string })?.message ?? t("Failed to save policy."));
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
      setRowError((err as { message?: string })?.message ?? t("Failed to update status."));
    } finally {
      setBusyType(null);
    }
  }

  async function deletePolicy(p: LeavePolicy) {
    if (!(await confirmDialog(t("Delete \"{name}\"? This cannot be undone.", { name: p.leave_type_display })))) return;
    setBusyType(p.leave_type);
    setRowError(null);
    try {
      await clientApi.delete(API.leave.policyDetail(p.leave_type));
      refetch();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? t("Failed to delete leave type."));
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
    if (!label) e.leave_type_label = t("Display name is required.");
    else if (!LEAVE_NAME_RE.test(label)) e.leave_type_label = t("Display name can only contain letters, spaces, and hyphens — no numbers or special characters.");
    if (createForm.annual_days < 0) e.annual_days = t("Annual days cannot be negative.");
    if (createForm.can_carry_forward && createForm.max_carry_forward_days < 1) e.max_carry_forward_days = t("Must be at least 1 when carry forward is enabled.");
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
      setCreateError((err as { message?: string })?.message ?? t("Failed to create leave type."));
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
      <LeaveTypeStats list={list} loading={loading} />
      <LeaveTypesTable
        list={list} loading={loading} error={error} rowError={rowError} busyType={busyType}
        onCreate={openCreate} onEdit={openEdit} onToggle={toggleActive} onDelete={deletePolicy}
      />

      {/* Edit Modal */}
      {editing && (
        <Modal
          title={<><i className="ti ti-beach" style={{ marginRight: 8 }} />{t("Edit: {name}", { name: editing.leave_type_display })}</>}
          onClose={closeEdit}
          maxWidth={480}
          footer={
            <>
              <button className="btn btn-ghost" onClick={closeEdit}>{t("Cancel")}</button>
              <button className="btn btn-filled" onClick={saveEdit} disabled={isSaving}>
                {isSaving ? <><Spin />&nbsp;{t("Saving…")}</> : t("Save Changes")}
              </button>
            </>
          }
        >
          {saveError && (
            <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>{saveError}</div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
            <div className="field-group mb-16">
              <label className="field-label">{t("Annual Days *")}</label>
              <input className={`field-input${errors.annual_days ? " field-error" : ""}`} type="number" min={0} step={0.5} value={form.annual_days} onChange={e => editField("annual_days", Number(e.target.value))} />
              {errors.annual_days && <p className="field-error-msg">{errors.annual_days}</p>}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">{t("Accrual")}</label>
              <select className="field-input field-select" value={form.accrual_frequency} onChange={e => editField("accrual_frequency", e.target.value)}>
                <option value="annual">{t("Annual (lump sum on Jan 1)")}</option>
                <option value="monthly">{t("Monthly (1/12th each month)")}</option>
              </select>
            </div>
            <div className="field-group mb-16">
              <label className="field-label">{t("Max Carry Fwd (days)")}</label>
              <input className={`field-input${errors.max_carry_forward_days ? " field-error" : ""}`} type="number" min={0} value={form.max_carry_forward_days} onChange={e => editField("max_carry_forward_days", Number(e.target.value))} disabled={!form.can_carry_forward} />
              {errors.max_carry_forward_days && <p className="field-error-msg">{errors.max_carry_forward_days}</p>}
            </div>
          </div>
          <div className="field-group mb-16">
            <label className="field-label">{t("Policy Note")}</label>
            <textarea className="field-input" rows={3} value={form.policy_note} onChange={e => editField("policy_note", e.target.value)} placeholder={t("Visible to employees when applying for leave")} style={{ resize: "none" }} />
          </div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 4 }}>
            <label className="module-check">
              <input type="checkbox" checked={form.can_carry_forward} onChange={e => editField("can_carry_forward", e.target.checked)} />
              <span>{t("Allow Carry Forward")}</span>
            </label>
            <label className="module-check">
              <input type="checkbox" checked={form.is_active} onChange={e => editField("is_active", e.target.checked)} />
              <span>{t("Active")}</span>
            </label>
          </div>
        </Modal>
      )}

      {/* Create Modal */}
      {isCreating && (
        <Modal
          title={<><i className="ti ti-plus" style={{ marginRight: 8 }} />{t("Add Leave Type")}</>}
          onClose={closeCreate}
          maxWidth={480}
          footer={
            <>
              <button className="btn btn-ghost" onClick={closeCreate}>{t("Cancel")}</button>
              <button className="btn btn-filled" onClick={submitCreate} disabled={isSubmitting}>
                {isSubmitting ? <><Spin />&nbsp;{t("Creating…")}</> : t("Create Leave Type")}
              </button>
            </>
          }
        >
          {createError && (
            <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>{createError}</div>
          )}
          <div className="field-group mb-16">
            <label className="field-label">{t("Display Name *")}</label>
            <input
              className={`field-input${createErrors.leave_type_label ? " field-error" : ""}`}
              type="text"
              placeholder={t("e.g. Compensatory Off")}
              value={createForm.leave_type_label}
              onChange={e => createField("leave_type_label", sanitizeLeaveName(e.target.value))}
            />
            {createErrors.leave_type_label
              ? <p className="field-error-msg">{createErrors.leave_type_label}</p>
              : createForm.leave_type_label.trim() && (
                <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
                  {t("Key:")} <code>{createForm.leave_type_label.trim().toLowerCase().replace(/[\s-]+/g, "_")}</code>
                </p>
              )
            }
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
            <div className="field-group mb-16">
              <label className="field-label">{t("Annual Days *")}</label>
              <input className={`field-input${createErrors.annual_days ? " field-error" : ""}`} type="number" min={0} step={0.5} value={createForm.annual_days} onChange={e => createField("annual_days", Number(e.target.value))} />
              {createErrors.annual_days && <p className="field-error-msg">{createErrors.annual_days}</p>}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">{t("Accrual")}</label>
              <select className="field-input field-select" value={createForm.accrual_frequency} onChange={e => createField("accrual_frequency", e.target.value)}>
                <option value="annual">{t("Annual (lump sum on Jan 1)")}</option>
                <option value="monthly">{t("Monthly (1/12th each month)")}</option>
              </select>
            </div>
            <div className="field-group mb-16">
              <label className="field-label">{t("Max Carry Fwd (days)")}</label>
              <input className={`field-input${createErrors.max_carry_forward_days ? " field-error" : ""}`} type="number" min={0} value={createForm.max_carry_forward_days} onChange={e => createField("max_carry_forward_days", Number(e.target.value))} disabled={!createForm.can_carry_forward} />
              {createErrors.max_carry_forward_days && <p className="field-error-msg">{createErrors.max_carry_forward_days}</p>}
            </div>
          </div>
          <div className="field-group mb-16">
            <label className="field-label">{t("Policy Note")}</label>
            <textarea className="field-input" rows={3} value={createForm.policy_note} onChange={e => createField("policy_note", e.target.value)} placeholder={t("Visible to employees when applying for leave")} style={{ resize: "none" }} />
          </div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 4 }}>
            <label className="module-check">
              <input type="checkbox" checked={createForm.can_carry_forward} onChange={e => createField("can_carry_forward", e.target.checked)} />
              <span>{t("Allow Carry Forward")}</span>
            </label>
            <label className="module-check">
              <input type="checkbox" checked={createForm.is_active} onChange={e => createField("is_active", e.target.checked)} />
              <span>{t("Active")}</span>
            </label>
          </div>
        </Modal>
      )}
    </>
  );
}
