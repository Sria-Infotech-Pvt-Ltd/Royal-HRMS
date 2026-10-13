"use client";

// ESS "Documents" — a small, self-service "submit a document for
// verification" screen. Deliberately NOT the org-wide Document Center
// (app/dashboard/documents, still reachable from the sidebar's "Document
// Center" nav item and from PoliciesAssetsTab's "Company policies" card):
// that is a shared policies/forms/templates repository. This screen is a
// personal, per-employee record of "I submitted document X for HR to verify"
// — the employee can open the file again and delete it until HR verifies it.

import { useState } from "react";
import { useMyDocuments, type ApiDocumentSubmission, type DocumentStatus } from "@/hooks/useMyDocuments";
import { formatDate } from "@/lib/formatDate";
import ConfirmModal from "@/components/ConfirmModal";
import DocumentSubmissionForm from "./DocumentSubmissionForm";

const STATUS_BADGE: Record<DocumentStatus, string> = {
  pending:  "badge-warn",
  verified: "badge-success",
  rejected: "badge-error",
};

const ICON_BUTTON_STYLE = {
  display: "inline-flex", alignItems: "center", justifyContent: "center", width: 30, height: 30,
  border: "1px solid var(--outline-v)", borderRadius: 8, background: "var(--surface)",
  color: "var(--on-variant)", cursor: "pointer", textDecoration: "none", flexShrink: 0,
} as const;

export default function MyDocumentsTab() {
  const { submissions, loading, error, submitting, submitError, submit, remove, deletingId, deleteError } = useMyDocuments();
  const [pendingDelete, setPendingDelete] = useState<ApiDocumentSubmission | null>(null);

  async function handleConfirmDelete() {
    if (!pendingDelete) return;
    await remove(pendingDelete.id);
    setPendingDelete(null);
  }

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>Documents</h2>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--on-variant)" }}>
          Upload and manage verified employee documents.
        </p>
      </div>

      <DocumentSubmissionForm submitting={submitting} submitError={submitError} onSubmit={submit} />

      <MyDocumentsList
        submissions={submissions}
        loading={loading}
        error={error ?? deleteError}
        onDelete={setPendingDelete}
      />

      {pendingDelete && (
        <ConfirmModal
          title="Delete this document?"
          body={`This will permanently delete "${pendingDelete.file_name}" and the file stored with it. This cannot be undone.`}
          confirmLabel="Delete"
          danger
          saving={deletingId === pendingDelete.id}
          onConfirm={handleConfirmDelete}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  );
}

function MyDocumentsList({ submissions, loading, error, onDelete }: {
  submissions: ApiDocumentSubmission[];
  loading: boolean;
  error: string | null;
  onDelete: (doc: ApiDocumentSubmission) => void;
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
          {submissions.map(doc => <DocumentRow key={doc.id} doc={doc} onDelete={onDelete} />)}
        </div>
      )}
    </div>
  );
}

function DocumentRow({ doc, onDelete }: { doc: ApiDocumentSubmission; onDelete: (doc: ApiDocumentSubmission) => void }) {
  // HR-verified documents are part of the employee's record — the server refuses to delete them, so no button.
  const canDelete = doc.status !== "verified";
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid var(--outline-v)", gap: 12 }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{doc.file_name}</div>
        <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
          {doc.category_display} · {doc.expiry_date ? formatDate(doc.expiry_date) : "No expiry"}
          {!doc.file_url && " · File not stored (submitted before uploads were kept)"}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <span className={`badge ${STATUS_BADGE[doc.status]}`}>{doc.status_display.toUpperCase()}</span>
        {doc.file_url && (
          <a href={doc.file_url} target="_blank" rel="noopener noreferrer" title="View document" aria-label={`View ${doc.file_name}`} style={ICON_BUTTON_STYLE}>
            <i className="ti ti-eye" style={{ fontSize: 16 }} />
          </a>
        )}
        {canDelete && (
          <button
            type="button"
            title="Delete document"
            aria-label={`Delete ${doc.file_name}`}
            onClick={() => onDelete(doc)}
            style={{ ...ICON_BUTTON_STYLE, color: "var(--error)" }}
          >
            <i className="ti ti-trash" style={{ fontSize: 16 }} />
          </button>
        )}
      </div>
    </div>
  );
}
