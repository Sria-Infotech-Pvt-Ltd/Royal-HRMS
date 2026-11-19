"use client";

import { useState, useCallback } from "react";
import Modal from "@/components/Modal";
import { useAttendanceCorrection } from "@/hooks/useAttendanceCorrection";
import type { PunchType, CorrectionReason } from "@/types/attendance";
import DateInput from "@/components/shared/DateInput";
import { tr } from "@/lib/i18n/tr";

interface Props {
  isOpen:    boolean;
  date:      string;
  onClose:   () => void;
  onSuccess: () => void;
}

const REASON_OPTIONS: { value: CorrectionReason; label: string }[] = [
  { value: "biometric_error",  get label() { return tr("Device malfunction / biometric error"); } },
  { value: "forgot_to_punch",  get label() { return tr("Forgot to punch"); }                      },
  { value: "field_work",       get label() { return tr("Work from field (client visit)"); }        },
  { value: "system_downtime",  get label() { return tr("System / server downtime"); }              },
  { value: "other",            get label() { return tr("Other"); }                                 },
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

  // Modal renders its footer through a React portal straight to
  // document.body, so a <form> wrapping <Modal> never actually contains
  // the footer in the real DOM -- a type="submit" button there has no
  // form owner (button.form === null) and native submission silently does
  // nothing. The id/form attribute pair associates them by id instead of
  // DOM nesting, which works regardless of the portal.
  const formId = "correction-form";

  return (
    <form id={formId} onSubmit={handleSubmit}>
      <Modal
        title={
          <>
            <i className="ti ti-file-description" style={{ marginRight: 8, color: "var(--warn)" }} />
            {tr("Attendance Correction Request")}
          </>
        }
        onClose={onClose}
        maxWidth={480}
        footer={
          <>
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={isSubmitting}>{tr("Cancel")}</button>
            <button type="submit" form={formId} className="btn btn-filled" disabled={isSubmitting}>
              {isSubmitting
                ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> {tr("Submitting…")}</>
                : <><i className="ti ti-send" /> {tr("Submit Request")}</>}
            </button>
          </>
        }
      >
        <div className="alert alert-warn mb-16">
          <i className="ti ti-alert-triangle" />
          <span>{tr("Submit a correction for a missed or incorrect punch. Your manager will review within the regularization cutoff window (7 days after month end).")}</span>
        </div>

        <div className="form-row cols-2">
          <div className="field-group">
            <label className="field-label">{tr("Date")}</label>
            <DateInput className="field-input" value={date} readOnly onChange={() => undefined} />
          </div>
          <div className="field-group">
            <label className="field-label">{tr("Punch Type")}</label>
            <select className="field-input field-select" value={punchType} onChange={e => setPunchType(e.target.value as PunchType)}>
              <option value="IN">{tr("Clock In (IN)")}</option>
              <option value="OUT">{tr("Clock Out (OUT)")}</option>
              <option value="BOTH">{tr("Both IN & OUT")}</option>
            </select>
          </div>
        </div>

        <div className="form-row cols-2">
          {showIn && (
            <div className="field-group">
              <label className="field-label">{tr("Correct In Time")}</label>
              <input type="time" className="field-input" value={correctInTime} onChange={e => setCorrectInTime(e.target.value)} required />
            </div>
          )}
          {showOut && (
            <div className="field-group">
              <label className="field-label">{tr("Correct Out Time")}</label>
              <input type="time" className="field-input" value={correctOutTime} onChange={e => setCorrectOutTime(e.target.value)} required />
            </div>
          )}
        </div>

        <div className="field-group mb-16">
          <label className="field-label">{tr("Reason")}</label>
          <select className="field-input field-select" value={reason} onChange={e => setReason(e.target.value as CorrectionReason)}>
            {REASON_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <div className="field-group">
          <label className="field-label">{tr("Additional Notes (optional)")}</label>
          <textarea className="field-input" style={{ minHeight: 72 }} placeholder={tr("Describe the situation…")} value={notes} onChange={e => setNotes(e.target.value)} />
        </div>
      </Modal>
    </form>
  );
}
