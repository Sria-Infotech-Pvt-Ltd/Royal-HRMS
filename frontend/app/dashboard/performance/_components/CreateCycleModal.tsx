"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export default function CreateCycleModal({ onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [selfDue, setSelfDue] = useState("");
  const [managerDue, setManagerDue] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleCreate() {
    setErr(null);
    setSaving(true);
    try {
      await clientApi.post(API.performance.cycles, {
        name, period_start: periodStart, period_end: periodEnd,
        self_review_due: selfDue, manager_review_due: managerDue,
      });
      onCreated();
    } catch (error: unknown) {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setErr(msg ?? "Failed to create review cycle.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ width: "min(480px, 95vw)" }}>
        <div className="modal-header">
          <div className="modal-title">New review cycle</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          {err && <div className="alert alert-error mb-16">{err}</div>}
          <div className="field-group mb-16">
            <label className="field-label">Name</label>
            <input className="field-input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Q4 2026" />
          </div>
          <div className="form-row cols-2">
            <div className="field-group mb-16">
              <label className="field-label">Period Start</label>
              <input className="field-input" type="date" value={periodStart} onChange={e => setPeriodStart(e.target.value)} />
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Period End</label>
              <input className="field-input" type="date" value={periodEnd} onChange={e => setPeriodEnd(e.target.value)} />
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Self-Review Due</label>
              <input className="field-input" type="date" value={selfDue} onChange={e => setSelfDue(e.target.value)} />
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Manager Review Due</label>
              <input className="field-input" type="date" value={managerDue} onChange={e => setManagerDue(e.target.value)} />
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button
            className="btn btn-filled"
            onClick={handleCreate}
            disabled={saving || !name.trim() || !periodStart || !periodEnd || !selfDue || !managerDue}
          >
            {saving ? "Creating…" : "Create Cycle"}
          </button>
        </div>
      </div>
    </div>
  );
}
