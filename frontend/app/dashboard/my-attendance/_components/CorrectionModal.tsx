"use client";

import { useState, useCallback } from "react";
import Modal from "@/components/Modal";
import { useAttendanceCorrection } from "@/hooks/useAttendanceCorrection";
import type { PunchType, CorrectionReason } from "@/types/attendance";

interface Props {
  isOpen:    boolean;
  date:      string;
  onClose:   () => void;
  onSuccess: () => void;
}

const REASON_OPTIONS: { value: CorrectionReason; label: string }[] = [
  { value: "biometric_error",  label: "Device malfunction / biometric error" },
  { value: "forgot_to_punch",  label: "Forgot to punch"                      },
  { value: "field_work",       label: "Work from field (client visit)"        },
  { value: "system_downtime",  label: "System / server downtime"              },
  { value: "other",            label: "Other"                                 },
];

export default function CorrectionModal({ isOpen, date, onClose, onSuccess }: Props) {
  const [punchType,      setPunchType]      = useState<PunchType>("IN");
  const [correctInTime,  setCorrectInTime]  = useState("09:05");
  const [correctOutTime, setCorrectOutTime] = useState("18:10");
  const [reason,         setReason]         = useState<CorrectionReason>("biometric_error");
  const [notes,          setNotes]          = useState("");

  const handleSuccess = useCallback(() => { onSuccess(); onClose(); }, [onSuccess, onClose]);
  const { submitCorrection, isSubmitting } = useAttendanceCorrection({ onSuccess: handleSuccess });

  if (!isOpen) return null;

  const showIn  = punchType === "IN"  || punchType === "BOTH";
  const showOut = punchType === "OUT" || punchType === "BOTH";

  async function handleSubmit(e: { preventDefault(): void }) {
    e.preventDefault();
    await submitCorrection({
      date,
      punch_type:        punchType,
      correct_in_time:   showIn  ? correctInTime  : undefined,
      correct_out_time:  showOut ? correctOutTime : undefined,
      reason,
      notes: notes.trim() || undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit}>
      <Modal
        title={
          <>
            <i className="ti ti-file-description" style={{ marginRight: 8, color: "var(--warn)" }} />
            Attendance Correction Request
          </>
        }
        onClose={onClose}
        maxWidth={480}
        footer={
          <>
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={isSubmitting}>Cancel</button>
            <button type="submit" className="btn btn-filled" disabled={isSubmitting}>
              {isSubmitting
                ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Submitting…</>
                : <><i className="ti ti-send" /> Submit Request</>}
            </button>
          </>
        }
      >
        <div className="alert alert-warn mb-16">
          <i className="ti ti-alert-triangle" />
          <span>Submit a correction for a missed or incorrect punch. Your manager will review within the regularization cutoff window (7 days after month end).</span>
        </div>

        <div className="form-row cols-2">
          <div className="field-group">
            <label className="field-label">Date</label>
            <input type="date" className="field-input" value={date} readOnly />
          </div>
          <div className="field-group">
            <label className="field-label">Punch Type</label>
            <select className="field-input" value={punchType} onChange={e => setPunchType(e.target.value as PunchType)}>
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
              <input type="time" className="field-input" value={correctInTime} onChange={e => setCorrectInTime(e.target.value)} required />
            </div>
          )}
          {showOut && (
            <div className="field-group">
              <label className="field-label">Correct Out Time</label>
              <input type="time" className="field-input" value={correctOutTime} onChange={e => setCorrectOutTime(e.target.value)} required />
            </div>
          )}
        </div>

        <div className="field-group mb-16">
          <label className="field-label">Reason</label>
          <select className="field-input" value={reason} onChange={e => setReason(e.target.value as CorrectionReason)}>
            {REASON_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <div className="field-group">
          <label className="field-label">Additional Notes (optional)</label>
          <textarea className="field-input" style={{ minHeight: 72 }} placeholder="Describe the situation…" value={notes} onChange={e => setNotes(e.target.value)} />
        </div>
      </Modal>
    </form>
  );
}
