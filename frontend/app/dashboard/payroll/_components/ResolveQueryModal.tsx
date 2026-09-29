"use client";

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import type { PayslipQuery } from "@/types/payroll";

// Shared by Payroll → Payslip Queries and Approvals → Payslip Requests — the
// EXISTING POST /payroll/queries/<id>/resolve/ flow, one implementation only.
export default function ResolveQueryModal({ query, onResolved, onClose }: { query: PayslipQuery; onResolved: () => void; onClose: () => void }) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState("");

  async function handleConfirm() {
    if (!note.trim()) { setApiError("Please enter a resolution note."); return; }
    setSaving(true);
    setApiError("");
    try {
      await clientApi.post(API.payroll.resolveQuery(query.id), { resolution_note: note.trim() });
      onResolved();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiError(msg ?? "Failed to resolve query. Please try again.");
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
            <div style={{ width: 36, height: 36, borderRadius: "50%", background: "var(--primary-container)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <i className="ti ti-message-circle" style={{ color: "var(--primary)", fontSize: 18 }} />
            </div>
            <div>
              <div className="modal-title">Resolve Payslip Query</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                Raised by {query.raised_by_name}
              </div>
            </div>
          </div>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="form-group">
            <label className="form-label">Employee&apos;s query</label>
            <div className="form-input" style={{ background: "var(--bg-low)", minHeight: 60, whiteSpace: "pre-wrap" }}>
              {query.description}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Resolution note <span style={{ color: "var(--error)" }}>*</span></label>
            <textarea
              className="form-input"
              rows={3}
              placeholder="e.g. Corrected HRA calculation, revised payslip has been re-sent…"
              value={note}
              onChange={e => { setNote(e.target.value); setApiError(""); }}
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
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-filled" onClick={handleConfirm} disabled={saving || !note.trim()}>
            {saving ? <i className="ti ti-loader-2 animate-spin" /> : <i className="ti ti-check" />}
            {saving ? "Resolving…" : "Resolve Query"}
          </button>
        </div>
      </div>
    </div>
  );
}
