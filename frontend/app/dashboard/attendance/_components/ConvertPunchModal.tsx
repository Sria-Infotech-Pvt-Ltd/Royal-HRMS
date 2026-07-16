"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import type { InvalidPunch } from "@/types/attendance";

interface Props {
  punch:       InvalidPunch;
  onClose:     () => void;
  onConverted: () => void;
}

export default function ConvertPunchModal({ punch, onClose, onConverted }: Props) {
  const { showToast } = useToast();
  const [punchType, setPunchType]   = useState<"IN" | "OUT">("OUT");
  const [targetTime, setTargetTime] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState<string | null>(null);

  async function handleSubmit() {
    if (!targetTime) { setError("Please select the target time."); return; }
    setSubmitting(true);
    setError(null);
    try {
      await clientApi.post(API.attendance.invalidPunchConvert(punch.id), {
        target_punch_type: punchType,
        target_time:       targetTime,
      });
      showToast("Invalid punch converted. Attendance record recalculated.", "success");
      onConverted();
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? "Failed to convert invalid punch.";
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
            <i className="ti ti-replace" style={{ marginRight: 8, color: "var(--primary)" }} />
            Convert to Valid Punch
          </span>
          <button className="modal-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          {error && (
            <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> <span>{error}</span></div>
          )}

          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 12 }}>
            Device: {punch.device_id} · {punch.raw_time}
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Punch Type</label>
              <select className="field-input" value={punchType} onChange={e => setPunchType(e.target.value as "IN" | "OUT")}>
                <option value="IN">IN</option>
                <option value="OUT">OUT</option>
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Target Time</label>
              <input
                type="time"
                className="field-input"
                value={targetTime}
                onChange={e => setTargetTime(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting}>
            {submitting ? <><i className="ti ti-loader-2" /> Converting…</> : "Convert to Valid Punch"}
          </button>
        </div>
      </div>
    </div>
  );
}
