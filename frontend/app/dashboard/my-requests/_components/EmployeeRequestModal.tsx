"use client";

// "New request" modal for the ESS "Requests" tab — a generic employee
// request with no dedicated backend model of its own, same reuse pattern as
// AssetRequestModal.tsx / ProfileCorrectionModal.tsx: it submits through the
// existing HR Help support-request endpoint (topic + priority + message),
// with the request type and subject folded into the free-text message so
// nothing the employee typed is lost even where several request types map
// onto the same underlying HR_HELP_TOPIC_CHOICES value.

import { useState } from "react";
import RequestModal from "@/components/RequestModal";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

// Maps onto the real HR_HELP_TOPIC_CHOICES in apps/hrms/models.py. Only
// 'document_request' and 'payroll_query' have a dedicated topic that fits;
// "Benefits query" and "Workplace support" have no matching topic yet, so
// both fold into 'other' rather than inventing new topic choices for this.
const REQUEST_TYPES = [
  { value: "Employment letter", label: "Employment letter", topic: "document_request" },
  { value: "Benefits query",    label: "Benefits query",     topic: "other" },
  { value: "Payroll query",     label: "Payroll query",      topic: "payroll_query" },
  { value: "Workplace support", label: "Workplace support",  topic: "other" },
  { value: "Other",             label: "Other",              topic: "other" },
] as const;

const PRIORITIES = [
  { value: "low",    label: "Low" },
  { value: "normal", label: "Normal" },
  { value: "high",   label: "High" },
];

interface Props {
  onClose: () => void;
  onSubmitted: () => void;
}

export default function EmployeeRequestModal({ onClose, onSubmitted }: Props) {
  const [requestType, setRequestType] = useState<typeof REQUEST_TYPES[number]["value"]>(REQUEST_TYPES[0].value);
  const [subject, setSubject] = useState("");
  const [priority, setPriority] = useState("normal");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setError(null);
    if (!subject.trim()) { setError("Please enter a short summary."); return; }
    if (description.trim().length < 10) { setError("Please describe your request in at least 10 characters."); return; }
    setSubmitting(true);
    try {
      const selected = REQUEST_TYPES.find(t => t.value === requestType) ?? REQUEST_TYPES[0];
      const message = `Request type: ${selected.label}. Subject: ${subject.trim()}. ${description.trim()}`;
      await clientApi.post(API.hrHelp.list, { topic: selected.topic, priority, message });
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
      title={<><i className="ti ti-plus" /> New request</>}
      onClose={onClose}
      onSubmit={handleSubmit}
      submitting={submitting}
      error={error}
    >
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Request type</label>
          <select
            className="field-input field-select"
            value={requestType}
            onChange={e => setRequestType(e.target.value as typeof requestType)}
          >
            {REQUEST_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Subject</label>
          <input
            className="field-input"
            value={subject}
            onChange={e => setSubject(e.target.value)}
            placeholder="Short summary"
          />
        </div>
      </div>
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Priority</label>
          <select className="field-input field-select" value={priority} onChange={e => setPriority(e.target.value)}>
            {PRIORITIES.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>
      </div>
      <div className="field-group">
        <label className="field-label">Description</label>
        <textarea
          className="field-input"
          rows={4}
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="Describe your request"
        />
      </div>
    </RequestModal>
  );
}
