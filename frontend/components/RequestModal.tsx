"use client";

// Shared chrome for the ESS "request" modals (tax declaration, expense claim,
// asset request, profile correction, ...): identical title/subtitle header,
// error banner, and footer helper-text + Cancel + Submit actions. Each caller
// keeps its own field-specific state, validation, and submit logic — this
// component only renders the shell they all repeated. Not for arbitrary
// modals; only for ones that submit a request and show up in My Requests.

import type { ReactNode } from "react";
import Modal from "@/components/Modal";

const SUBTITLE = "Complete the required information. Your submission will appear in My Requests.";
const FOOTER_NOTE = "Submissions are routed for approval and retained in My Requests.";

interface RequestModalProps {
  title: ReactNode;
  onClose: () => void;
  onSubmit: () => void;
  submitting?: boolean;
  submitLabel?: string;
  submittingLabel?: ReactNode;
  /** Disables close (X + backdrop) independently of `submitting`; defaults to `submitting`. */
  closeDisabled?: boolean;
  error?: string | null;
  /** Override the standard footer helper text, if a caller ever needs to. */
  footerNote?: string;
  maxWidth?: number | string;
  children: ReactNode;
}

export default function RequestModal({
  title,
  onClose,
  onSubmit,
  submitting = false,
  submitLabel = "Submit request",
  submittingLabel,
  closeDisabled,
  error,
  footerNote = FOOTER_NOTE,
  maxWidth,
  children,
}: RequestModalProps) {
  return (
    <Modal
      title={
        <div>
          <div>{title}</div>
          <div style={{ fontSize: 12, fontWeight: 400, color: "var(--on-variant)", marginTop: 2 }}>
            {SUBTITLE}
          </div>
        </div>
      }
      onClose={onClose}
      closeDisabled={closeDisabled ?? submitting}
      maxWidth={maxWidth}
      footer={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", gap: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, color: "var(--on-variant)" }}>{footerNote}</span>
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn btn-ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button className="btn btn-filled" onClick={onSubmit} disabled={submitting}>
              {submitting
                ? (submittingLabel ?? <><i className="ti ti-loader-2 spin" /> Submitting…</>)
                : submitLabel}
            </button>
          </div>
        </div>
      }
    >
      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}
      {children}
    </Modal>
  );
}
