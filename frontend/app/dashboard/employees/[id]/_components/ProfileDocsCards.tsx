"use client";

import React, { useState } from "react";
import { type DocEntry } from "../../_data";
import DocPreviewModal from "@/components/DocPreviewModal";

function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const DOC_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

/* ── Employee Documents — 4-col card grid ───────────────────── */
export default function DocsCards({
  documents,
  onUpload,
  uploadingDocType,
  uploadError,
}: {
  documents: DocEntry[];
  onUpload?: (documentType: string, file: File) => void;
  uploadingDocType?: string | null;
  uploadError?: string;
}) {
  const [preview, setPreview] = useState<DocEntry | null>(null);

  function handleFileChange(documentType: string, e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (file && onUpload) onUpload(documentType, file);
  }

  return (
    <>
      {preview && preview.fileUrl && (
        <DocPreviewModal
          name={preview.name}
          fileName={preview.fileName}
          fileUrl={preview.fileUrl}
          fileSize={preview.fileSize}
          onClose={() => setPreview(null)}
        />
      )}

      <div>
        <div className="mb-5">
          <p className="text-[13px]" style={{ color: "var(--on-variant)" }}>
            All documents uploaded by the employee or{" "}
            <span className="font-semibold" style={{ color: "var(--primary)" }}>HR</span>
          </p>
          {uploadError && (
            <p className="text-[12.5px] font-medium mt-2" style={{ color: "var(--error)" }}>
              {uploadError}
            </p>
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: "1rem" }}>
          {documents.map((doc) => {
            const uploaded  = !!doc.fileUrl;
            const uploading = uploadingDocType === doc.documentType;
            return (
              <div
                key={doc.name}
                className="flex items-center gap-3 px-3.5 py-3 rounded-xl border bg-[var(--surface)]"
                style={{ borderColor: "var(--outline-v)" }}
              >
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: uploaded ? "rgba(23,144,90,0.10)" : "var(--bg-mid)" }}
                >
                  <i
                    className={`ti ${uploading ? "ti-loader-2 animate-spin" : uploaded ? "ti-file-check" : "ti-file-off"} text-[18px]`}
                    style={{ color: uploaded ? "#17905a" : "var(--on-variant)" }}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold truncate leading-snug" style={{ color: "var(--on-bg)" }}>
                    {doc.name}
                  </p>
                  <p className="text-[11.5px] leading-snug" style={{ color: "var(--on-variant)" }}>
                    {uploading
                      ? "Uploading…"
                      : uploaded
                        ? `${doc.uploadedOn}${doc.fileSize ? ` · ${fmtBytes(doc.fileSize)}` : ""}`
                        : "Not uploaded"}
                  </p>
                </div>
                <label
                  title={uploaded ? "Replace document" : "Upload document"}
                  suppressHydrationWarning
                  className={`w-7 h-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-mid)] flex-shrink-0 transition-colors ${uploading ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
                  style={{ color: "var(--on-variant)" }}
                >
                  <i className={`ti ${uploaded ? "ti-refresh" : "ti-upload"} text-[15px]`} />
                  <input
                    type="file"
                    accept={DOC_ACCEPT}
                    className="hidden"
                    disabled={uploading}
                    onChange={(e) => handleFileChange(doc.documentType, e)}
                  />
                </label>
                <button
                  title={uploaded ? "Preview document" : "Not uploaded"}
                  disabled={!uploaded}
                  onClick={() => uploaded && setPreview(doc)}
                  suppressHydrationWarning
                  className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-mid)] flex-shrink-0 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  style={{ color: uploaded ? "var(--primary)" : "var(--on-variant)" }}
                >
                  <i className="ti ti-eye text-[15px]" />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
