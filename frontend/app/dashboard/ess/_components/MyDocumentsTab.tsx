"use client";

// ESS "Documents" — a small, self-service "submit a document for
// verification" screen. Deliberately NOT the org-wide Document Center
// (app/dashboard/documents, still reachable from the sidebar's "Document
// Center" nav item and from PoliciesAssetsTab's "Company policies" card):
// that is a shared policies/forms/templates repository with real file
// upload/preview/delete. This screen is a personal, per-employee record of
// "I submitted document X for HR to verify" — per the spec, no file bytes
// are stored, only submission metadata (category, filename, expiry).

import { useRef, useState } from "react";
import { useMyDocuments, type ApiDocumentSubmission, type DocumentCategory, type DocumentStatus } from "@/hooks/useMyDocuments";
import { formatDate } from "@/lib/formatDate";

const CATEGORY_OPTIONS: { value: DocumentCategory; label: string }[] = [
  { value: "identity",   label: "Identity" },
  { value: "education",  label: "Education" },
  { value: "employment", label: "Employment" },
  { value: "tax_proof",  label: "Tax proof" },
  { value: "benefits",   label: "Benefits" },
  { value: "other",      label: "Other" },
];

const STATUS_BADGE: Record<DocumentStatus, string> = {
  pending:  "badge-warn",
  verified: "badge-success",
  rejected: "badge-error",
};

export default function MyDocumentsTab() {
  const { submissions, loading, error, submitting, submitError, submit } = useMyDocuments();

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>Documents</h2>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--on-variant)" }}>
          Upload and manage verified employee documents.
        </p>
      </div>

      <SubmissionForm submitting={submitting} submitError={submitError} onSubmit={submit} />

      <MyDocumentsList submissions={submissions} loading={loading} error={error} />
    </div>
  );
}

function SubmissionForm({ submitting, submitError, onSubmit }: {
  submitting: boolean;
  submitError: string | null;
  onSubmit: (input: { category: DocumentCategory; file_name: string; expiry_date: string | null }) => Promise<boolean>;
}) {
  const [category, setCategory]     = useState<DocumentCategory | "">("");
  const [expiryDate, setExpiryDate] = useState("");
  const [fileName, setFileName]     = useState("");
  const [formError, setFormError]   = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0];
    // Spec: "This demo records submission metadata; it does not retain the
    // file" — only the picked filename is captured, nothing is uploaded.
    setFileName(picked ? picked.name : "");
  }

  async function handleSubmit() {
    setFormError(null);
    if (!category) {
      setFormError("Please choose a document category.");
      return;
    }
    if (!fileName) {
      setFormError("Please choose a file.");
      return;
    }
    const ok = await onSubmit({ category, file_name: fileName, expiry_date: expiryDate || null });
    if (ok) {
      setCategory("");
      setExpiryDate("");
      setFileName("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className={`upload-zone${fileName ? " upload-zone--active" : ""}`} style={{ marginBottom: 20, cursor: "default" }}>
      <i className="ti ti-cloud-upload" />
      <p style={{ fontWeight: 600, color: "var(--on-bg)", marginBottom: 2 }}>
        Submit a document for verification
      </p>
      <small style={{ display: "block", marginBottom: 16 }}>
        PDF, JPG or PNG · Maximum 10 MB. This demo records submission metadata; it does not retain the file.
      </small>

      {(formError || submitError) && (
        <div className="alert alert-error" style={{ marginBottom: 16, textAlign: "left" }}>
          {formError ?? submitError}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, textAlign: "left", marginBottom: 16 }}>
        <div className="field-group">
          <label className="field-label">Document category</label>
          <select
            className="field-input field-select"
            value={category}
            onChange={e => setCategory(e.target.value as DocumentCategory)}
          >
            <option value="">Choose category</option>
            {CATEGORY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Expiry date (if applicable)</label>
          <input
            type="date"
            className="field-input"
            value={expiryDate}
            onChange={e => setExpiryDate(e.target.value)}
          />
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        onChange={handleFilePicked}
        style={{ display: "none" }}
        id="my-documents-file-input"
      />
      <label htmlFor="my-documents-file-input" className="btn btn-ghost" style={{ cursor: "pointer" }}>
        <i className="ti ti-file" /> {fileName || "Choose file"}
      </label>

      <div style={{ marginTop: 16 }}>
        <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Submitting…" : "Submit for verification"}
        </button>
      </div>
    </div>
  );
}

function MyDocumentsList({ submissions, loading, error }: {
  submissions: ApiDocumentSubmission[];
  loading: boolean;
  error: string | null;
}) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-files" /> My documents</div>
        <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "var(--on-variant)" }}>
          Verification state and expiry information.
        </p>
      </div>
      {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}
      {loading ? (
        <div className="empty-state">
          <i className="ti ti-loader-2 spin" />
          <h3>Loading documents…</h3>
        </div>
      ) : submissions.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-files" />
          <h3>No documents submitted yet</h3>
          <p>Documents you submit for verification will appear here.</p>
        </div>
      ) : (
        <div style={{ padding: "4px 24px 16px" }}>
          {submissions.map(doc => (
            <div key={doc.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid var(--outline-v)", gap: 12 }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{doc.file_name}</div>
                <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
                  {doc.category_display} · {doc.expiry_date ? formatDate(doc.expiry_date) : "No expiry"}
                </div>
              </div>
              <span className={`badge ${STATUS_BADGE[doc.status]}`}>{doc.status_display.toUpperCase()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
