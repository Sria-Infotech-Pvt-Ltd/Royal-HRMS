"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import { rejectionProblem } from "@/lib/faceRejection";

interface RejectReasonModalProps {
  employeeName: string;
  isSaving: boolean;
  /** An error from the server for this rejection; shown inside the dialog so the request and the typed reason survive. */
  serverError: string;
  onSubmit: (remarks: string) => void;
  onCancel: () => void;
}

/** Asks the approver why a Face ID registration is being rejected. The reason is required and is sent to the employee. */
export default function RejectReasonModal({ employeeName, isSaving, serverError, onSubmit, onCancel }: RejectReasonModalProps) {
  const [remarks, setRemarks] = useState("");
  const [localError, setLocalError] = useState("");

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const problem = rejectionProblem(remarks);
    setLocalError(problem);
    if (!problem) onSubmit(remarks.trim());
  }

  const message = localError || serverError;
  return (
    <Modal title={`Reject Face ID registration — ${employeeName}`} onClose={onCancel} closeDisabled={isSaving}>
      <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
        <label className="field-label" htmlFor="face-rejection-reason">Reason (the employee will see this)</label>
        <textarea id="face-rejection-reason" className="field-input" rows={4} maxLength={1000} value={remarks}
          onChange={event => setRemarks(event.target.value)} />
        {message && <p role="alert" style={{ color: "var(--error)", margin: 0 }}>{message}</p>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={isSaving}>Cancel</button>
          <button type="submit" className="btn btn-filled" disabled={isSaving}>{isSaving ? "Rejecting…" : "Reject registration"}</button>
        </div>
      </form>
    </Modal>
  );
}
