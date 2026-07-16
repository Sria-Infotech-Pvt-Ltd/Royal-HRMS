"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { ImportResult, ImportRowError } from "@/types/attendance";

interface Props {
  onClose:    () => void;
  onImported: (result: ImportResult) => void;
}

// Backend sends a plain string for exceptions, but a DRF serializer errors
// dict (e.g. { date: ["Invalid format."] }) for per-field validation failures.
// Flatten either shape to a single displayable line.
function formatRowError(errors: ImportRowError["errors"]): string {
  if (typeof errors === "string") return errors;
  return Object.entries(errors)
    .map(([field, messages]) => `${field}: ${Array.isArray(messages) ? messages.join(" ") : String(messages)}`)
    .join(" · ");
}

export default function ImportModal({ onClose, onImported }: Props) {
  const [file,       setFile]       = useState<File | null>(null);
  const [dragOver,   setDragOver]   = useState(false);
  const [uploading,  setUploading]  = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [result,     setResult]     = useState<ImportResult | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) { setFile(dropped); setError(null); }
  }

  async function handleUpload() {
    if (!file) { setError("Please select a CSV file to import."); return; }
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await clientApi.post<{ data: ImportResult }>(API.attendance.import, formData);
      setResult(response.data?.data ?? null);
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? "Failed to import attendance file.";
      setError(message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <span className="modal-title">
            <i className="ti ti-upload" style={{ marginRight: 8, color: "var(--primary)" }} />
            Import Attendance
          </span>
          <button className="modal-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          {!result && (
            <>
              <div className="alert alert-info mb-16">
                <i className="ti ti-info-circle" />
                <span>
                  <strong>Required columns:</strong> employee_id, date, punch_in, punch_out — CSV only, max 5 MB.
                  <code style={{ display: "block", marginTop: 6, fontSize: 11 }}>
                    EMP001,2026-07-02,09:05,18:15
                  </code>
                </span>
              </div>

              {error && (
                <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> <span>{error}</span></div>
              )}

              <div
                className="upload-zone mb-16"
                style={{ cursor: "pointer", borderColor: dragOver ? "var(--primary)" : undefined }}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
              >
                <i className="ti ti-folder-open" />
                <p style={{ fontWeight: 500, marginBottom: 4 }}>
                  {file ? file.name : "Click to select file or drag & drop"}
                </p>
                <small>CSV — max 5 MB</small>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                style={{ display: "none" }}
                onChange={e => { setFile(e.target.files?.[0] ?? null); setError(null); }}
              />
            </>
          )}

          {result && (
            <>
              <div className={`alert ${result.failed > 0 ? "alert-warn" : "alert-info"} mb-16`}>
                <i className={`ti ${result.failed > 0 ? "ti-alert-triangle" : "ti-circle-check"}`} />
                <span>
                  {result.success} of {result.total_rows} row(s) imported successfully.
                  {result.failed > 0 && ` ${result.failed} row(s) failed.`}
                </span>
              </div>

              {result.failed > 0 && (
                <div>
                  <button className="btn btn-outline btn-sm mb-16" onClick={() => setShowErrors(v => !v)}>
                    <i className={`ti ti-chevron-${showErrors ? "up" : "down"}`} /> {showErrors ? "Hide" : "Show"} row errors
                  </button>
                  {showErrors && (
                    <div className="table-wrap" style={{ maxHeight: 220, overflowY: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
                      <table>
                        <thead>
                          <tr><th>Row</th><th>Error</th></tr>
                        </thead>
                        <tbody>
                          {result.errors.map(e => (
                            <tr key={e.row}>
                              <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{e.row}</td>
                              <td style={{ fontSize: 12 }}>{formatRowError(e.errors)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        <div className="modal-footer">
          {!result ? (
            <>
              <button className="btn btn-ghost" onClick={onClose} disabled={uploading}>Cancel</button>
              <button className="btn btn-filled" onClick={handleUpload} disabled={uploading}>
                {uploading
                  ? <><i className="ti ti-loader-2" /> Uploading…</>
                  : <><i className="ti ti-upload" /> Upload &amp; Process</>
                }
              </button>
            </>
          ) : (
            <button className="btn btn-filled" onClick={() => onImported(result)}>Done</button>
          )}
        </div>
      </div>
    </div>
  );
}
