"use client";

// "Request profile correction" modal — submits via the generic HR Help
// support-request endpoint (topic='profile_correction'), same reuse pattern
// as AssetRequestModal.tsx: no dedicated correction-request model exists,
// so the section/field/new value/reason fields are folded into
// HRHelpRequest.message rather than adding a new Django model for this one
// free-text request.

import { useState } from "react";
import RequestModal from "@/components/RequestModal";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { CORRECTION_SECTIONS, fieldsForSection } from "./profileCorrectionFields";

export const PROFILE_CORRECTION_TOPIC = "profile_correction";

interface Props {
  onClose: () => void;
  onSubmitted: () => void;
}

export default function ProfileCorrectionModal({ onClose, onSubmitted }: Props) {
  const [section, setSection] = useState(CORRECTION_SECTIONS[0].value);
  const [field, setField] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function changeSection(value: string) {
    setSection(value);
    setField("");
  }

  async function handleSubmit() {
    setError(null);
    if (!fieldsForSection(section).includes(field)) { setError("Please choose which field needs to change."); return; }
    if (reason.trim().length < 10) { setError("Please describe the reason in at least 10 characters."); return; }
    setSubmitting(true);
    try {
      const message = `Section: ${section}. Field to change: ${field}. Reason: ${reason.trim()}`;
      await clientApi.post(API.hrHelp.list, { topic: PROFILE_CORRECTION_TOPIC, priority: "normal", message });
      onSubmitted();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg ?? "Failed to submit request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <RequestModal
      title={<><i className="ti ti-edit" /> Profile correction</>}
      onClose={onClose}
      onSubmit={handleSubmit}
      submitting={submitting}
      error={error}
    >
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Section</label>
          <select className="field-input field-select" value={section} onChange={e => changeSection(e.target.value)} suppressHydrationWarning>
            {CORRECTION_SECTIONS.map(entry => <option key={entry.value} value={entry.value}>{entry.value}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Field to change</label>
          <select className="field-input field-select" value={field} onChange={e => setField(e.target.value)} suppressHydrationWarning>
            <option value="">Select a field…</option>
            {fieldsForSection(section).map(name => <option key={name} value={name}>{name}</option>)}
          </select>
        </div>
      </div>
      <div className="field-group">
        <label className="field-label">Reason</label>
        <textarea
          className="field-input"
          rows={3}
          value={reason}
          onChange={e => setReason(e.target.value)}
          placeholder="Reason for correction"
        />
      </div>
    </RequestModal>
  );
}
