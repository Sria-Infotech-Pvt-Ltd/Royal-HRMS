"use client";

import { useState } from "react";
import DocPreviewModal from "@/components/DocPreviewModal";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";

export interface UploadedDoc { id: string; document_type: string; document_type_display: string; file?: string; file_name: string; uploaded_at: string; }

const PAN_RE = /^[A-Za-z]{5}[0-9]{4}[A-Za-z]$/;
const INP = "field-input";
const Req = () => <span style={{ color: "var(--error, #dc2626)", marginLeft: 2 }}>*</span>;

// ── Tab: Documents ────────────────────────────────────────────────────────────
// Pure/prop-driven — no internal API calls, everything happens via the
// callback props. Shared by the self-service onboarding wizard
// (app/onboarding/page.tsx) and the HR-completes-onboarding wizard
// (app/dashboard/employees/[id]/onboarding/page.tsx).

export default function TabDocuments({
  docTypes, docs, uploadedTypes, uploading, fileRefs, onUpload,
  panNumber, onPanNumberChange, onPanCardUpload, onPanValidationError, panErr, panSaving,
}: {
  docTypes: DocumentTypeConfig[];
  docs: UploadedDoc[];
  uploadedTypes: Set<string>;
  uploading: string | null;
  fileRefs: React.RefObject<Record<string, HTMLInputElement | null>>;
  onUpload: (docType: string, file: File) => void;
  panNumber: string;
  onPanNumberChange: (v: string) => void;
  onPanCardUpload: (file: File) => void;
  onPanValidationError: (msg: string) => void;
  panErr: string | null;
  panSaving: boolean;
}) {
  const [preview, setPreview] = useState<UploadedDoc | null>(null);

  return (
    <>
      {preview && preview.file && (
        <DocPreviewModal
          name={preview.document_type_display}
          fileName={preview.file_name}
          fileUrl={preview.file}
          onClose={() => setPreview(null)}
        />
      )}
      <div>
        <p style={{ color: "var(--on-variant)", marginBottom: "1.25rem", fontSize: ".9rem", lineHeight: 1.6 }}>
          Upload clear scans or photos. Accepted: PDF, JPG, PNG · Max 5 MB each.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: ".875rem" }}>
          {docTypes.map(dt => {
            const uploaded     = uploadedTypes.has(dt.type_key);
            const uploaded_doc = docs.find(d => d.document_type === dt.type_key);
            const isPan        = dt.type_key === "pan_card";
            const isUploading  = uploading === dt.type_key || (isPan && panSaving);
            const panBlocked   = isPan && !PAN_RE.test(panNumber.trim());
            return (
              <div key={dt.type_key} style={{
                padding: "1rem 1.25rem", borderRadius: 12,
                border: `1.5px solid ${uploaded ? "var(--success)" : "var(--outline-v)"}`,
                background: uploaded ? "var(--success-c)" : "#fff",
                transition: "all 0.2s",
              }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 36, height: 36, borderRadius: 9, background: uploaded ? "var(--success)" : "var(--bg-high)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <i className={uploaded ? "ti ti-file-check" : "ti ti-file-upload"} style={{ color: uploaded ? "#fff" : "var(--on-variant)", fontSize: 18 }} />
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: ".9rem", color: "var(--on-bg)" }}>{dt.label}</div>
                      {uploaded && uploaded_doc && (
                        <div style={{ fontSize: ".78rem", color: "var(--success)", marginTop: 2 }}>
                          <i className="ti ti-check" style={{ fontSize: 11 }} /> {uploaded_doc.file_name}
                        </div>
                      )}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: ".5rem", alignItems: "center", flexShrink: 0 }}>
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png"
                      style={{ display: "none" }}
                      ref={el => { fileRefs.current[dt.type_key] = el; }}
                      onChange={e => {
                        const file = e.target.files?.[0];
                        if (file) {
                          if (isPan) onPanCardUpload(file);
                          else onUpload(dt.type_key, file);
                        }
                        e.target.value = "";
                      }}
                    />
                    {uploaded && uploaded_doc?.file && (
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: ".83rem" }}
                        onClick={() => setPreview(uploaded_doc)}
                        type="button"
                      >
                        <i className="ti ti-eye" style={{ fontSize: 13 }} /> View
                      </button>
                    )}
                    <button
                      className="btn btn-ghost"
                      style={{ fontSize: ".83rem", borderColor: uploaded ? "var(--success)" : undefined, color: uploaded ? "var(--success)" : undefined }}
                      onClick={() => {
                        // Validate before ever opening the file picker, not just
                        // via a disabled attribute — a disabled button swallows
                        // the click entirely, leaving the user with no visible
                        // reason why "Upload" does nothing (see handlePanCardUpload,
                        // which already has these exact messages but never used to
                        // run because the click that would trigger it was blocked
                        // one step earlier).
                        if (panBlocked) {
                          onPanValidationError(
                            panNumber.trim()
                              ? "Enter a valid PAN (e.g. ABCDE1234F) — 5 letters, 4 digits, 1 letter."
                              : "Enter your PAN number before uploading the PAN card.",
                          );
                          return;
                        }
                        fileRefs.current[dt.type_key]?.click();
                      }}
                      disabled={isUploading}
                      type="button"
                    >
                      {isUploading
                        ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 13 }} /> Uploading…</>
                        : uploaded ? "Replace" : "Upload"
                      }
                    </button>
                  </div>
                </div>
                {isPan && (
                  <div style={{ marginTop: ".75rem", paddingTop: ".75rem", borderTop: "1px solid var(--outline-v)" }}>
                    <label className="field-label">PAN Number<Req /></label>
                    <input
                      className={INP}
                      style={{ maxWidth: 220 }}
                      maxLength={10}
                      value={panNumber}
                      onChange={e => onPanNumberChange(e.target.value.toUpperCase())}
                      placeholder="e.g. ABCDE1234F"
                    />
                    {panErr ? (
                      <div style={{ fontSize: ".78rem", color: "var(--error, #dc2626)", marginTop: 4 }}>{panErr}</div>
                    ) : (
                      <div style={{ fontSize: ".72rem", color: "var(--on-variant)", marginTop: 4 }}>
                        Checked against every other employee before the upload goes through — enter it first.
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
