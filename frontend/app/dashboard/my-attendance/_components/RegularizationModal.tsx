"use client";

import { useState } from "react";

import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import type { CorrectionRequest, CorrectionPunchType, CorrectionReason } from "@/types/myAttendance";

interface Props {
  onClose:    () => void;
  onSuccess?: () => void;
  date?:      string;
}

type NormalisedError = { message?: string };

const REASON_OPTIONS: { value: CorrectionReason; label: string }[] = [
  { value: "biometric_error",  label: "Device malfunction / biometric error" },
  { value: "forgot_to_punch",  label: "Forgot to punch"                      },
  { value: "field_work",       label: "Work from field (client visit)"        },
  { value: "system_downtime",  label: "System / server downtime"              },
  { value: "other",            label: "Other"                                 },
];

function todayString() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function RegularizationModal({ onClose, onSuccess, date }: Props) {
  const { showToast } = useToast();

  const [formDate,        setFormDate]        = useState(date ?? todayString());
  const [punchType,       setPunchType]       = useState<CorrectionPunchType>("IN");
  const [correctInTime,   setCorrectInTime]   = useState("09:05");
  const [correctOutTime,  setCorrectOutTime]  = useState("18:10");
  const [reason,          setReason]          = useState<CorrectionReason>("biometric_error");
  const [notes,           setNotes]           = useState("");
  const [submitting,      setSubmitting]      = useState(false);

  const showIn  = punchType === "IN"   || punchType === "BOTH";
  const showOut = punchType === "OUT"  || punchType === "BOTH";

  async function handleSubmit(e: { preventDefault(): void }) {
    e.preventDefault();
    setSubmitting(true);

    const body: CorrectionRequest = {
      date:       formDate,
      punch_type: punchType,
      reason,
    };
    if (showIn)  body.correct_in_time  = correctInTime;
    if (showOut) body.correct_out_time = correctOutTime;
    if (notes.trim()) body.notes = notes.trim();

    try {
      const res = await clientApi.post(API.attendance.correction, body);
      const msg = (res.data as { message?: string })?.message ?? "Correction request submitted successfully.";
      showToast(msg, "success");
      onSuccess?.();
      onClose();
    } catch (err: unknown) {
      const e = err as NormalisedError;
      showToast(e?.message ?? "Failed to submit correction request.", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={ev => { if (ev.target === ev.currentTarget) onClose(); }}>
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <span className="modal-title">
            <i className="ti ti-file-description" style={{ marginRight: 8, color: "var(--warn)" }} />
            Attendance Correction Request
          </span>
          <button className="modal-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="alert alert-warn mb-16">
              <i className="ti ti-alert-triangle" />
              <span>
                Submit a correction for a missed or incorrect punch. Your manager will review and approve
                within the regularization cutoff window (7 days after month end).
              </span>
            </div>

            <div className="form-row cols-2">
              <div className="field-group">
                <label className="field-label">Date</label>
                <input
                  type="date"
                  className="field-input"
                  value={formDate}
                  onChange={e => setFormDate(e.target.value)}
                  required
                />
              </div>
              <div className="field-group">
                <label className="field-label">Punch Type</label>
                <select
                  className="field-input"
                  value={punchType}
                  onChange={e => setPunchType(e.target.value as CorrectionPunchType)}
                >
                  <option value="IN">Clock In (IN)</option>
                  <option value="OUT">Clock Out (OUT)</option>
                  <option value="BOTH">Both IN &amp; OUT</option>
                </select>
              </div>
            </div>

            <div className="form-row cols-2">
              {showIn && (
                <div className="field-group">
                  <label className="field-label">Correct In Time</label>
                  <input
                    type="time"
                    className="field-input"
                    value={correctInTime}
                    onChange={e => setCorrectInTime(e.target.value)}
                    required={showIn}
                  />
                </div>
              )}
              {showOut && (
                <div className="field-group">
                  <label className="field-label">Correct Out Time</label>
                  <input
                    type="time"
                    className="field-input"
                    value={correctOutTime}
                    onChange={e => setCorrectOutTime(e.target.value)}
                    required={showOut}
                  />
                </div>
              )}
            </div>

            <div className="field-group mb-16">
              <label className="field-label">Reason</label>
              <select
                className="field-input"
                value={reason}
                onChange={e => setReason(e.target.value as CorrectionReason)}
              >
                {REASON_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            <div className="field-group">
              <label className="field-label">Additional Notes (optional)</label>
              <textarea
                className="field-input"
                style={{ minHeight: 72 }}
                placeholder="Describe the situation…"
                value={notes}
                onChange={e => setNotes(e.target.value)}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-filled" disabled={submitting}>
              {submitting
                ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Submitting…</>
                : <><i className="ti ti-send" /> Submit Request</>
              }
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
