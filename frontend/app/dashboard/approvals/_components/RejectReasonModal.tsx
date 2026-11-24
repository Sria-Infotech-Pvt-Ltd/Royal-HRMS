"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import { useT } from "@/hooks/useI18n";
import { REJECTION_REASON_REQUIRED } from "@/lib/faceRejection";

interface RejectReasonModalProps {
  employeeName: string;
  isSaving: boolean;
  /** An error from the server for this rejection; shown inside the dialog so the request and the typed reason survive. */
  serverError: string;
  onSubmit: (remarks: string) => void;
  onCancel: () => void;
  /** Wording for other workflows (for example "Send timesheet back"). Left out, the Face ID registration wording is used. */
  wording?: Partial<RejectReasonWording>;
}

export interface RejectReasonWording {
  /** The dialog title is `${title} — ${employeeName}`. */
  title: string;
  fieldLabel: string;
  actionLabel: string;
  busyLabel: string;
  requiredMessage: string;
}

const FACE_ID_WORDING: RejectReasonWording = {
  title: "Reject Face ID registration",
  fieldLabel: "Reason (the employee will see this)",
  actionLabel: "Reject registration",
  busyLabel: "Rejecting…",
  requiredMessage: REJECTION_REASON_REQUIRED,
};

/** Asks the approver for a written reason before a request is turned down or sent back. The reason is required and is sent to
 *  the employee. Used for Face ID registrations and, with its own wording, for timesheets. */
export default function RejectReasonModal({ employeeName, isSaving, serverError, onSubmit, onCancel, wording }: RejectReasonModalProps) {
  const t = useT();
  const [remarks, setRemarks] = useState("");
  const [localError, setLocalError] = useState("");
  const text = { ...FACE_ID_WORDING, ...wording };

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const problem = remarks.trim() ? "" : t(text.requiredMessage);
    setLocalError(problem);
    if (!problem) onSubmit(remarks.trim());
  }

  const message = localError || serverError;
  return (
    <Modal title={t("{title} — {name}", { title: t(text.title), name: employeeName })} onClose={onCancel} closeDisabled={isSaving}>
      <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
        <label className="field-label" htmlFor="face-rejection-reason">{t(text.fieldLabel)}</label>
        <textarea id="face-rejection-reason" className="field-input" rows={4} maxLength={1000} value={remarks}
          onChange={event => setRemarks(event.target.value)} />
        {message && <p role="alert" style={{ color: "var(--error)", margin: 0 }}>{message}</p>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={isSaving}>{t("Cancel")}</button>
          <button type="submit" className="btn btn-filled" disabled={isSaving}>{isSaving ? t(text.busyLabel) : t(text.actionLabel)}</button>
        </div>
      </form>
    </Modal>
  );
}
