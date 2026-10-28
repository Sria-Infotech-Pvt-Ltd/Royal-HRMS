"use client";

// Upload one proof document (receipt, certificate, statement) for a claimed tax item, with the
// policy / account / receipt number quoted on it so payroll can cross-check.

import { useRef, useState, type ChangeEvent } from "react";
import Modal from "@/components/Modal";
import FieldError from "@/components/shared/FieldError";
import type { DocumentSubmissionInput } from "@/hooks/useMyDocuments";
import { ACCEPTED_EXTENSIONS, ACCEPTED_TYPES_LABEL, MAX_FILE_SIZE_LABEL, formatFileSize, validateDocumentFile } from "@/lib/documentFile";
import type { TaxProofItem } from "@/types/taxDeclaration";

interface Props {
  item: TaxProofItem;
  submit: (input: DocumentSubmissionInput) => Promise<boolean>;
  submitting: boolean;
  submitError: string | null;
  onClose: () => void;
  onUploaded: () => void;
}

export default function TaxProofUploadModal({ item, submit, submitting, submitError, onClose, onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [referenceNumber, setReferenceNumber] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFilePicked(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0];
    if (!picked) return;
    const problem = validateDocumentFile(picked);
    setFileError(problem);
    setFile(problem ? null : picked);
    if (problem && fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleUpload() {
    // A file that failed the size/type check is dropped, so `file` is empty too: keep saying why instead of
    // replacing the real reason (e.g. "File is too large") with "Please choose the proof document."
    if (!file) { setFileError(previous => previous ?? "Please choose the proof document."); return; }
    const isUploaded = await submit({ file, tax_item: item.key, reference_number: referenceNumber.trim() });
    if (isUploaded) onUploaded();
  }

  return (
    <Modal
      title={<><i className="ti ti-upload" style={{ marginRight: 8 }} />Upload proof — {item.label}</>}
      onClose={onClose}
      closeDisabled={submitting}
      maxWidth={520}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="btn btn-filled" onClick={handleUpload} disabled={submitting}>{submitting ? "Uploading…" : "Upload proof"}</button>
        </>
      }
    >
      <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--on-variant)" }}>Proof needed: {item.proof}.</p>
      {submitError && !fileError && <div className="alert alert-error" style={{ marginBottom: 12 }}>{submitError}</div>}

      {item.asksReference && (
        <div className="field-group" style={{ marginBottom: 12 }}>
          <label className="field-label" htmlFor="tax-proof-reference">Policy / account / receipt number (optional)</label>
          <input
            id="tax-proof-reference" className="field-input" maxLength={60} value={referenceNumber}
            onChange={event => setReferenceNumber(event.target.value)}
          />
        </div>
      )}

      <div className="field-group">
        <label className="field-label">Document file</label>
        <input ref={fileInputRef} id="tax-proof-file" type="file" accept={ACCEPTED_EXTENSIONS.join(",")} onChange={handleFilePicked} style={{ display: "none" }} />
        <label htmlFor="tax-proof-file" className="field-input" style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", height: 40 }}>
          <i className="ti ti-paperclip" />
          <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file ? file.name : "Choose file"}</span>
          {file && <span style={{ fontSize: 11, color: "var(--on-variant)" }}>{formatFileSize(file.size)}</span>}
        </label>
        <FieldError message={fileError} />
        <span style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 6 }}>Accepted: {ACCEPTED_TYPES_LABEL} · Max {MAX_FILE_SIZE_LABEL}</span>
      </div>
    </Modal>
  );
}
