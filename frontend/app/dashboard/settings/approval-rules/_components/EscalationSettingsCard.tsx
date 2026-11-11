"use client";

// Settings → Approval Rules → Automatic Reminders & Escalation (company-wide).
// Off until an administrator switches it on. Days are working days of the
// current approver (their week-offs and branch holidays are skipped).

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import {
  apiMessage, escalationTimeline, toEscalationForm, validateEscalation,
  type EscalationForm, type EscalationSettings, type PersonRef,
} from "@/lib/approvalWorkflows";

export default function EscalationSettingsCard() {
  const { data, loading, error, status } = useFetch<EscalationSettings>(API.approvals.escalationSettings);
  const canEdit = data?.can_edit === true;
  const { data: heads } = useFetch<PersonRef[]>(canEdit ? API.approvals.escalationHeadCandidates : null);

  // Unsaved edits; until the first edit the form shows the saved settings.
  const [draft, setDraft] = useState<EscalationForm | null>(null);
  const form = draft ?? (data ? toEscalationForm(data) : null);
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState("");
  const [saved, setSaved] = useState(false);

  if (status === 403) return null;
  if (loading || !form) {
    return error ? <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error}</div> : null;
  }

  const errors = validateEscalation(form);
  const headName = heads?.find(h => h.id === form.escalation_head)?.name
    ?? (data?.escalation_head?.id === form.escalation_head ? data?.escalation_head?.name : "") ?? "";
  const timeline = escalationTimeline(form, headName);

  function set<K extends keyof EscalationForm>(key: K, value: EscalationForm[K]) {
    if (form) setDraft({ ...form, [key]: value });
    setSaved(false);
  }

  async function save() {
    if (!form || Object.keys(errors).length) return;
    setSaving(true);
    setApiError("");
    try {
      await clientApi.put(API.approvals.escalationSettings, { ...form, escalation_head: form.escalation_head || null });
      setSaved(true);
    } catch (err) {
      setApiError(apiMessage(err, "Failed to save escalation settings."));
    } finally {
      setSaving(false);
    }
  }

  const num = (key: "reminder_after_days" | "first_escalation_after_days" | "second_escalation_after_days",
               label: string, hint: string) => (
    <div className="field-group">
      <label className="field-label" htmlFor={`esc-${key}`}>{label}</label>
      <input
        id={`esc-${key}`}
        type="number"
        min={0}
        max={30}
        className="field-input"
        value={Number.isNaN(form[key]) ? "" : form[key]}
        disabled={!canEdit}
        onChange={e => set(key, e.target.value === "" ? NaN : Number(e.target.value))}
      />
      <div className="text-[11px] text-[var(--on-variant)] mt-1">{hint}</div>
      {errors[key] && <div className="text-[12px] text-red-600 mt-1" role="alert">{errors[key]}</div>}
    </div>
  );

  return (
    <div className="settings-card" style={{ marginTop: 16 }} data-testid="escalation-settings">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 15, color: "var(--on-bg)" }}>
            <i className="ti ti-alarm" style={{ marginRight: 6, color: "var(--primary)" }} />
            Automatic Reminders &amp; Escalation
          </div>
          <div className="text-[12px] text-[var(--on-variant)] mt-1">
            Pending leave and attendance requests remind the approver, then move up the chain. Days are working days;
            each step happens once per approval stage, and the count restarts when the request reaches HR.
          </div>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, whiteSpace: "nowrap" }}>
          <input
            type="checkbox"
            checked={form.is_enabled}
            disabled={!canEdit}
            onChange={e => set("is_enabled", e.target.checked)}
            aria-label="Enable automatic escalation"
          />
          {form.is_enabled ? "On" : "Off"}
        </label>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14, marginTop: 16 }}>
        {num("reminder_after_days", "Reminder after (working days)", "0 = no reminder")}
        {num("first_escalation_after_days", "First escalation after (working days)", "To the approver's reporting manager")}
        {num("second_escalation_after_days", "Second escalation after (more working days)", "Counted after the first; 0 = none")}
        <div className="field-group">
          <label className="field-label" htmlFor="esc-head">Escalation head (HR Head / Admin Head)</label>
          <select
            id="esc-head"
            className="field-input field-select"
            value={form.escalation_head}
            disabled={!canEdit}
            onChange={e => set("escalation_head", e.target.value)}
          >
            <option value="">— Not set (second escalation skipped) —</option>
            {data?.escalation_head && !heads?.some(h => h.id === data.escalation_head?.id) && (
              <option value={data.escalation_head.id}>{data.escalation_head.name}</option>
            )}
            {(heads ?? []).map(h => (
              <option key={h.id} value={h.id}>{h.name}{h.employee_id ? ` (${h.employee_id})` : ""}</option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ display: "flex", gap: 18, marginTop: 12, fontSize: 13 }}>
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={form.applies_to_leave} disabled={!canEdit}
                 onChange={e => set("applies_to_leave", e.target.checked)} />
          Leave requests
        </label>
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={form.applies_to_attendance} disabled={!canEdit}
                 onChange={e => set("applies_to_attendance", e.target.checked)} />
          Attendance corrections &amp; late justifications
        </label>
      </div>
      {errors.applies_to_leave && <div className="text-[12px] text-red-600 mt-1" role="alert">{errors.applies_to_leave}</div>}

      <ol className="text-[12px] text-[var(--on-variant)]" style={{ marginTop: 14, paddingLeft: 18, listStyle: "decimal" }}
          data-testid="escalation-timeline">
        {timeline.map(s => <li key={`${s.day}-${s.text}`}><strong>Day {s.day}:</strong> {s.text}</li>)}
      </ol>

      {apiError && <div className="alert alert-error" style={{ marginTop: 12 }}><i className="ti ti-alert-circle" /> {apiError}</div>}
      {canEdit && (
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 10, marginTop: 14 }}>
          {saved && <span className="text-[12px] text-green-700"><i className="ti ti-check" /> Saved</span>}
          <button className="btn btn-primary" onClick={save} disabled={saving || Object.keys(errors).length > 0}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save Escalation Settings"}
          </button>
        </div>
      )}
    </div>
  );
}
