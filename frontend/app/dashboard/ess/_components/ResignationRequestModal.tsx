"use client";

// Self-service "Resignation request" modal for the ESS "Employment" tab —
// deliberately NOT app/dashboard/separation/_components/SeparationFormModal.tsx,
// which is the full HR/admin-facing form (create/edit modes, employee picker,
// file upload, multi-column grids used by Separation & Exit and by
// profile/_components/SeparationCard.tsx). This is a focused, employee-only
// shape with exactly the fields an employee filing their own resignation
// needs, submitted through the same real endpoint (POST /separation/requests/,
// separation_type='resignation') those other entry points already use.
//
// The backend's `reason` field is a fixed choice enum (see
// SEPARATION_REASON_CHOICES in apps/hrms/models.py) with a free-text
// `reason_note` required only when reason='other' — there is no free-text
// "reason" column. Rather than reproduce that whole choice list here (which
// the reference design doesn't show), this always submits reason='other'
// and carries the employee's own words in `reason_note`, exactly like the
// 'other' path already supported by the full separation form.

import { useState } from "react";
import RequestModal from "@/components/RequestModal";
import ConfirmModal from "@/components/ConfirmModal";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

const NOTICE_PERIOD_OPTIONS = [15, 30, 45, 60, 90];

interface Props {
  defaultNoticePeriodDays: number | null;
  onClose: () => void;
  onSubmitted: () => void;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function ResignationRequestModal({ defaultNoticePeriodDays, onClose, onSubmitted }: Props) {
  const [lastDay, setLastDay] = useState("");
  const [noticePeriodDays, setNoticePeriodDays] = useState(defaultNoticePeriodDays || 30);
  const [reason, setReason] = useState("");
  const [handoverNotes, setHandoverNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  function validate(): boolean {
    setError(null);
    if (!lastDay) { setError("Please select your proposed last day."); return false; }
    if (lastDay < todayIso()) { setError("Your proposed last day cannot be in the past."); return false; }
    if (reason.trim().length < 10) { setError("Please describe your reason in at least 10 characters."); return false; }
    return true;
  }

  async function handleSubmit() {
    if (validate()) setShowConfirm(true);
  }

  async function confirmSubmit() {
    setShowConfirm(false);
    setSubmitting(true);
    try {
      await clientApi.post(API.separation.list, {
        separation_type: "resignation",
        reason: "other",
        reason_note: reason.trim(),
        request_date: todayIso(),
        proposed_last_working_day: lastDay,
        notice_period_days: noticePeriodDays,
        comments: handoverNotes.trim(),
      });
      onSubmitted();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg ?? "Failed to submit request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
    <RequestModal
      title={<><i className="ti ti-logout" /> Resignation request</>}
      onClose={onClose}
      onSubmit={handleSubmit}
      submitting={submitting}
      error={error}
    >
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Proposed last day</label>
          <input
            type="date"
            className="field-input"
            min={todayIso()}
            value={lastDay}
            onChange={e => setLastDay(e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">Notice period</label>
          <select
            className="field-input field-select"
            value={noticePeriodDays}
            onChange={e => setNoticePeriodDays(Number(e.target.value))}
          >
            {NOTICE_PERIOD_OPTIONS.map(days => (
              <option key={days} value={days}>{days} days</option>
            ))}
          </select>
        </div>
      </div>
      <div className="field-group mb-16">
        <label className="field-label">Reason</label>
        <textarea
          className="field-input"
          rows={3}
          value={reason}
          onChange={e => setReason(e.target.value)}
          placeholder="Describe your reason"
        />
      </div>
      <div className="field-group">
        <label className="field-label">Handover notes</label>
        <textarea
          className="field-input"
          rows={3}
          value={handoverNotes}
          onChange={e => setHandoverNotes(e.target.value)}
          placeholder="Key responsibilities and handover plan"
        />
      </div>
    </RequestModal>

    {showConfirm && (
      <ConfirmModal
        title="Submit this resignation request?"
        body={`This submits a formal resignation with a proposed last day of ${lastDay} (${noticePeriodDays}-day notice) for HR approval.`}
        confirmLabel="Submit Resignation"
        danger
        saving={submitting}
        onConfirm={confirmSubmit}
        onCancel={() => setShowConfirm(false)}
      />
    )}
    </>
  );
}
