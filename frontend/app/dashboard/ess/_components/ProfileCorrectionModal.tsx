"use client";

// "Request profile correction" modal — submits via the generic HR Help support-request endpoint (topic='profile_correction').
// The section / field / reason are folded into HRHelpRequest.message. For a field HR can apply in one step (the server lists them at
// GET /hr-help/change-fields/) the employee also types the new value, which HR then approves and the server writes to the record.

import { useState } from "react";
import RequestModal from "@/components/RequestModal";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { ProfileChangeField } from "@/types/hrHelp";
import { CORRECTION_SECTIONS, fieldsForSection } from "./profileCorrectionFields";
import ProfileChangeValueInput from "./ProfileChangeValueInput";

export const PROFILE_CORRECTION_TOPIC = "profile_correction";

interface Props {
  onClose: () => void;
  onSubmitted: () => void;
}

export default function ProfileCorrectionModal({ onClose, onSubmitted }: Props) {
  const [section, setSection] = useState(CORRECTION_SECTIONS[0].value);
  const [field, setField] = useState("");
  const [newValue, setNewValue] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: changeFields } = useFetch<ProfileChangeField[]>(API.hrHelp.changeFields);
  const spec = (changeFields ?? []).find(candidate => candidate.section === section && candidate.label === field) ?? null;

  function changeSection(value: string) {
    setSection(value);
    setField("");
    setNewValue("");
  }

  function changeField(value: string) {
    setField(value);
    setNewValue("");
  }

  async function handleSubmit() {
    setError(null);
    if (!fieldsForSection(section).includes(field)) { setError("Please choose which field needs to change."); return; }
    if (spec && !newValue.trim()) { setError(`Enter the new ${spec.label.toLowerCase()}.`); return; }
    if (reason.trim().length < 10) { setError("Please describe the reason in at least 10 characters."); return; }
    setSubmitting(true);
    try {
      const message = `Section: ${section}. Field to change: ${field}. Reason: ${reason.trim()}`;
      await clientApi.post(API.hrHelp.list, {
        topic: PROFILE_CORRECTION_TOPIC, priority: "normal", message, ...(spec ? { change_new_value: newValue.trim() } : {}),
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
    <RequestModal
      title={<><i className="ti ti-edit" /> Profile correction</>}
      onClose={onClose}
      onSubmit={handleSubmit}
      submitting={submitting}
      error={error}
    >
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Section<span style={{ color: "var(--error)" }}> *</span></label>
          <select className="field-input field-select" value={section} onChange={e => changeSection(e.target.value)} suppressHydrationWarning>
            {CORRECTION_SECTIONS.map(entry => <option key={entry.value} value={entry.value}>{entry.value}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Field to change<span style={{ color: "var(--error)" }}> *</span></label>
          <select className="field-input field-select" value={field} onChange={e => changeField(e.target.value)} suppressHydrationWarning>
            <option value="">Select a field…</option>
            {fieldsForSection(section).map(name => <option key={name} value={name}>{name}</option>)}
          </select>
        </div>
      </div>
      {spec && (
        <div className="field-group mb-16">
          <label className="field-label">Current {spec.label.toLowerCase()} (on record)</label>
          <input className="field-input" value={spec.current_value || "Not set"} readOnly aria-readonly="true" tabIndex={-1}
            style={{ background: "var(--surface-variant, #f4f4f6)", color: "var(--on-variant)", cursor: "not-allowed" }} />
        </div>
      )}
      {spec && (
        <div className="field-group mb-16">
          <label className="field-label">New {spec.label.toLowerCase()}<span style={{ color: "var(--error)" }}> *</span></label>
          <ProfileChangeValueInput spec={spec} value={newValue} onChange={setNewValue} />
          <p style={{ fontSize: 11, color: "var(--on-variant)", margin: "4px 0 0" }}>HR reviews this before your record is updated.</p>
        </div>
      )}
      <div className="field-group">
        <label className="field-label">Reason<span style={{ color: "var(--error)" }}> *</span></label>
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
