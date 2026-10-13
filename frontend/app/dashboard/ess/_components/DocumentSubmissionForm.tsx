"use client";

// The "submit a document for verification" form of the ESS Documents tab.
// The picked file is uploaded on submit. Before that, "View" opens the local
// file (a temporary in-browser URL) so the employee can confirm it is the
// right one; after submitting, the list below opens the stored copy.

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import type { DocumentCategory, DocumentSubmissionInput } from "@/hooks/useMyDocuments";
import DateInput from "@/components/shared/DateInput";
import {
  ACCEPTED_EXTENSIONS, ACCEPTED_TYPES_LABEL, MAX_FILE_SIZE_LABEL, formatFileSize, validateDocumentFile,
} from "@/lib/documentFile";

const CATEGORY_OPTIONS: { value: DocumentCategory; label: string }[] = [
  { value: "identity",   label: "Identity" },
  { value: "education",  label: "Education" },
  { value: "employment", label: "Employment" },
  { value: "tax_proof",  label: "Tax proof" },
  { value: "benefits",   label: "Benefits" },
  { value: "other",      label: "Other" },
];

// One height for every control in the row so the select, date box and file box line up.
const CONTROL_HEIGHT = 40;

interface Props {
  submitting: boolean;
  submitError: string | null;
  onSubmit: (input: DocumentSubmissionInput) => Promise<boolean>;
}

export default function DocumentSubmissionForm({ submitting, submitError, onSubmit }: Props) {
  const [category, setCategory]     = useState<DocumentCategory | "">("");
  const [expiryDate, setExpiryDate] = useState("");
  const [file, setFile]             = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [formError, setFormError]   = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Build (and always release) the temporary URL behind the "View" action.
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function clearFile() {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleFilePicked(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0];
    if (!picked) return;
    const problem = validateDocumentFile(picked);
    if (problem) {
      clearFile();
      setFormError(problem);
      return;
    }
    setFormError(null);
    setFile(picked);
  }

  async function handleSubmit() {
    setFormError(null);
    if (!category) {
      setFormError("Please choose a document category.");
      return;
    }
    if (!file) {
      setFormError("Please choose a file.");
      return;
    }
    const isSubmitted = await onSubmit({ category, file, expiry_date: expiryDate || null });
    if (isSubmitted) {
      setCategory("");
      setExpiryDate("");
      clearFile();
    }
  }

  return (
    <div className={`upload-zone${file ? " upload-zone--active" : ""}`} style={{ marginBottom: 20, cursor: "default" }}>
      <i className="ti ti-cloud-upload" />
      <p style={{ fontWeight: 600, color: "var(--on-bg)", marginBottom: 2 }}>
        Submit a document for verification
      </p>
      <small style={{ display: "block", marginBottom: 20 }}>
        HR will review your document and mark it verified or rejected. You can view or delete it below until it is verified.
      </small>

      <div style={{ maxWidth: 880, margin: "0 auto", textAlign: "left" }}>
        {(formError || submitError) && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>
            {formError ?? submitError}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
          <div className="field-group">
            <label className="field-label">Document category</label>
            <select
              className="field-input field-select"
              style={{ height: CONTROL_HEIGHT }}
              value={category}
              onChange={event => { setCategory(event.target.value as DocumentCategory); setFormError(null); }}
            >
              <option value="">Choose category</option>
              {CATEGORY_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </div>

          <div className="field-group">
            <label className="field-label">Expiry date (if applicable)</label>
            <DateInput className="field-input" style={{ height: CONTROL_HEIGHT }} value={expiryDate} onChange={setExpiryDate} />
          </div>

          <div className="field-group">
            <label className="field-label">Document file</label>
            <input
              ref={fileInputRef}
              id="my-documents-file-input"
              type="file"
              accept={ACCEPTED_EXTENSIONS.join(",")}
              onChange={handleFilePicked}
              style={{ display: "none" }}
            />
            <FileField file={file} previewUrl={previewUrl} onRemove={clearFile} />
            <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 6 }}>
              Accepted: {ACCEPTED_TYPES_LABEL} · Max {MAX_FILE_SIZE_LABEL}
            </div>
          </div>
        </div>

        <div style={{ marginTop: 20, textAlign: "center" }}>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Submitting…" : "Submit for verification"}
          </button>
        </div>
      </div>
    </div>
  );
}

function FileField({ file, previewUrl, onRemove }: {
  file: File | null;
  previewUrl: string | null;
  onRemove: () => void;
}) {
  const iconButtonStyle = {
    display: "inline-flex", alignItems: "center", justifyContent: "center", width: 26, height: 26,
    border: 0, borderRadius: 6, background: "none", color: "var(--on-variant)", cursor: "pointer", flexShrink: 0,
    textDecoration: "none",
  } as const;
  const iconStyle = { fontSize: 16, margin: 0, color: "inherit" } as const;

  if (!file) {
    return (
      <label
        htmlFor="my-documents-file-input"
        className="field-input"
        style={{ height: CONTROL_HEIGHT, display: "flex", alignItems: "center", gap: 8, cursor: "pointer", color: "var(--on-variant)" }}
      >
        <i className="ti ti-paperclip" style={iconStyle} />
        <span>Choose file</span>
      </label>
    );
  }

  return (
    <div
      className="field-input"
      style={{ height: CONTROL_HEIGHT, display: "flex", alignItems: "center", gap: 6, padding: "0 6px 0 12px" }}
    >
      <i className="ti ti-file" style={{ ...iconStyle, color: "var(--primary)" }} />
      <span
        title={file.name}
        style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
      >
        {file.name}
      </span>
      <span style={{ fontSize: 11, color: "var(--on-variant)", flexShrink: 0 }}>{formatFileSize(file.size)}</span>
      {previewUrl && (
        <a href={previewUrl} target="_blank" rel="noopener noreferrer" title="View file" aria-label="View file" style={iconButtonStyle}>
          <i className="ti ti-eye" style={iconStyle} />
        </a>
      )}
      <label htmlFor="my-documents-file-input" title="Change file" aria-label="Change file" style={iconButtonStyle}>
        <i className="ti ti-replace" style={iconStyle} />
      </label>
      <button type="button" onClick={onRemove} title="Remove file" aria-label="Remove file" style={iconButtonStyle}>
        <i className="ti ti-x" style={iconStyle} />
      </button>
    </div>
  );
}
