"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { CreateDocumentTypePayload } from "@/types/documentTypeConfig";

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

// Every document type is inherently file-typed — no field_type selector or
// dropdown-options input like AddFieldModal (those only make sense for
// text-like custom fields).
export default function AddDocumentTypeModal({ onClose, onCreated }: Props) {
  const [label, setLabel] = useState("");
  const [allowMultiple, setAllowMultiple] = useState(false);
  const [required, setRequired] = useState(false);
  const [labelError, setLabelError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function validate(): boolean {
    if (!label.trim()) {
      setLabelError("Label is required.");
      return false;
    }
    return true;
  }

  async function submit() {
    if (!validate()) return;
    setIsSubmitting(true);
    setSubmitError(null);
    const payload: CreateDocumentTypePayload = {
      label: label.trim(),
      required,
      allow_multiple: allowMultiple,
    };
    try {
      await clientApi.post(API.settings.documentTypes.list, payload);
      onCreated();
    } catch (err: unknown) {
      setSubmitError((err as { message?: string })?.message ?? "Failed to create document type.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-plus" style={{ marginRight: 8 }} />Add Document Type</>}
      onClose={onClose}
      maxWidth={460}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;Creating…</> : "Create Document Type"}
          </button>
        </>
      }
    >
      {submitError && (
        <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {submitError}
        </div>
      )}

      <div className="field-group mb-16">
        <label className="field-label">Document Label *</label>
        <input
          className={`field-input${labelError ? " field-error" : ""}`}
          type="text"
          placeholder="e.g. Voter ID Card"
          value={label}
          onChange={e => { setLabel(e.target.value); setLabelError(null); }}
        />
        {labelError && <p className="field-error-msg">{labelError}</p>}
        <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
          Accepts PDF, JPG, and PNG files up to 5 MB, same as every other document type.
        </p>
      </div>

      <label className="module-check mb-16">
        <input type="checkbox" checked={allowMultiple} onChange={e => setAllowMultiple(e.target.checked)} />
        <span>Allow multiple files</span>
      </label>

      <label className="module-check">
        <input type="checkbox" checked={required} onChange={e => setRequired(e.target.checked)} />
        <span>Required</span>
      </label>
    </Modal>
  );
}
