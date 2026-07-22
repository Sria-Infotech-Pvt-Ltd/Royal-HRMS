"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { PayrollCycle } from "@/types/payroll";

interface Props {
  cycle: PayrollCycle;
  onCancelled: () => void;
  onClose: () => void;
}

const PERIOD_LABEL = (c: PayrollCycle) =>
  new Date(c.cycle_start).toLocaleString("en-IN", { month: "long", year: "numeric" });

export default function CancelCycleModal({ cycle, onCancelled, onClose }: Props) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState("");

  async function handleConfirm() {
    if (!reason.trim()) { setApiError("Please enter a reason for cancellation."); return; }
    setSaving(true);
    setApiError("");
    try {
      await clientApi.post(API.payroll.cancelCycle(cycle.id), { reason: reason.trim() });
      onCancelled();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiError(msg ?? "Failed to cancel cycle. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.45)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        className="modal"
        style={{ maxWidth: 480, width: "100%", margin: 0 }}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: "50%", background: "var(--error-container)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <i className="ti ti-alert-triangle" style={{ color: "var(--error)", fontSize: 18 }} />
            </div>
            <div>
              <div className="modal-title">Cancel Payroll Cycle</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                {PERIOD_LABEL(cycle)} · {cycle.payslip_count} payslips
              </div>
            </div>
          </div>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="alert alert-error" style={{ fontSize: 13 }}>
            <i className="ti ti-info-circle" />
            <span>
              This cycle will be voided and <strong>cannot be restarted</strong>.
              Any approved expenses already included in this cycle will be <strong>unlinked</strong> and available for the next payroll run.
            </span>
          </div>

          <div className="form-group">
            <label className="form-label">Reason for cancellation <span style={{ color: "var(--error)" }}>*</span></label>
            <textarea
              className="form-input"
              rows={3}
              placeholder="e.g. Wrong cycle dates entered, payroll period needs to be restarted…"
              value={reason}
              onChange={e => { setReason(e.target.value); setApiError(""); }}
              style={{ resize: "vertical" }}
            />
          </div>

          {apiError && (
            <div className="alert alert-error" style={{ fontSize: 13 }}>
              <i className="ti ti-alert-circle" />
              <span>{apiError}</span>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Keep Cycle</button>
          <button className="btn btn-danger" onClick={handleConfirm} disabled={saving || !reason.trim()}>
            {saving ? <i className="ti ti-loader-2 animate-spin" /> : <i className="ti ti-trash" />}
            {saving ? "Cancelling…" : "Cancel This Cycle"}
          </button>
        </div>
      </div>
    </div>
  );
}
