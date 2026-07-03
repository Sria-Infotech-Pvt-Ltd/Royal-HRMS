"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import type { InvalidPunch } from "@/types/attendance";

interface Props {
  punch:      InvalidPunch;
  onClose:    () => void;
  onDiscarded: () => void;
}

const MAX_REMARKS = 500;

export default function DiscardPunchModal({ punch, onClose, onDiscarded }: Props) {
  const { showToast } = useToast();
  const [remarks, setRemarks]       = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      await clientApi.post(API.attendance.invalidPunchDiscard(punch.id), { remarks: remarks.trim() });
      showToast("Invalid punch discarded.", "success");
      onDiscarded();
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? "Failed to discard invalid punch.";
      setError(message);
      showToast(message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ maxWidth: 420 }}>
        <div className="modal-header">
          <span className="modal-title">
            <i className="ti ti-trash" style={{ marginRight: 8, color: "var(--error)" }} />
            Discard Invalid Punch
          </span>
          <button className="modal-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          {error && (
            <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> <span>{error}</span></div>
          )}

          <div className="alert alert-warn mb-16">
            <i className="ti ti-alert-triangle" />
            <span>Device: {punch.device_id} · {punch.raw_time} — this punch will be permanently discarded.</span>
          </div>

          <div className="field-group">
            <label className="field-label">Remarks (optional)</label>
            <textarea
              className="field-input"
              style={{ minHeight: 72 }}
              placeholder="e.g. Accidental duplicate punch"
              value={remarks}
              maxLength={MAX_REMARKS}
              onChange={e => setRemarks(e.target.value)}
            />
            <div style={{ textAlign: "right", fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
              {remarks.length}/{MAX_REMARKS}
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="btn btn-filled btn-danger" onClick={handleSubmit} disabled={submitting}>
            {submitting ? <><i className="ti ti-loader-2" /> Discarding…</> : "Discard Punch"}
          </button>
        </div>
      </div>
    </div>
  );
}
