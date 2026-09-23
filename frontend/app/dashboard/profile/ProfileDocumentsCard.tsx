"use client";

import type { DocEntry } from "@/app/dashboard/employees/_data";
import { DOC_ACCEPT, fmtBytes } from "./_profileClientData";

interface ProfileDocumentsCardProps {
  docEntries: (DocEntry & { docId?: number })[];
  uploadingDocType: string | null;
  onUploadDocument: (documentType: string, file: File) => void;
}

export default function ProfileDocumentsCard({ docEntries, uploadingDocType, onUploadDocument }: ProfileDocumentsCardProps) {
  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-file-description" />Documents</span>
      </div>
      <div className="card-body" style={{ padding: 0 }}>
        {docEntries.map((doc, i) => {
          const uploaded  = !!doc.fileUrl;
          const uploading = uploadingDocType === doc.documentType;
          return (
            <div key={doc.documentType} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 16px",
              borderBottom: i < docEntries.length - 1 ? "1px solid var(--bg-high)" : "none",
            }}>
              <i
                className={`ti ${uploading ? "ti-loader-2 spin" : uploaded ? "ti-file-check" : "ti-file-off"}`}
                style={{ color: uploaded ? "var(--success)" : "var(--on-variant)" }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, color: "var(--on-bg)" }}>{doc.name}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                  {uploading ? "Uploading…" : uploaded ? fmtBytes(doc.fileSize ?? 0) : "Not uploaded"}
                </div>
              </div>
              {uploaded ? (
                <a href={doc.fileUrl} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm" title="Preview document">
                  <i className="ti ti-eye" />
                </a>
              ) : (
                <button type="button" disabled className="btn btn-ghost btn-sm" title="Not uploaded" style={{ opacity: 0.3, cursor: "not-allowed" }}>
                  <i className="ti ti-eye" />
                </button>
              )}
              <label
                className="btn btn-ghost btn-sm"
                title={uploaded ? "Replace document" : "Upload document"}
                style={{ cursor: uploading ? "not-allowed" : "pointer", opacity: uploading ? 0.5 : 1 }}
                suppressHydrationWarning
              >
                <i className={`ti ${uploaded ? "ti-refresh" : "ti-upload"}`} />
                <input
                  type="file"
                  accept={DOC_ACCEPT}
                  className="hidden"
                  disabled={uploading}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (file) onUploadDocument(doc.documentType, file);
                  }}
                />
              </label>
            </div>
          );
        })}
      </div>
    </div>
  );
}
