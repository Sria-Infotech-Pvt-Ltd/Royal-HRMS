"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import { BulkImportResult } from "./_data";

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".csv", ".xlsx"];

type SampleFormat = "csv" | "xlsx";

interface Props {
  onClose:   () => void;
  onSuccess: () => void;
}

function validateFile(file: File): string | null {
  const hasAcceptedExtension = ACCEPTED_EXTENSIONS.some(ext =>
    file.name.toLowerCase().endsWith(ext)
  );
  if (!hasAcceptedExtension) return "Unsupported file type. Please upload a .csv or .xlsx file.";
  if (file.size > MAX_FILE_SIZE_BYTES) return "File is too large. Maximum allowed size is 5 MB.";
  return null;
}

export function CandidateBulkImportModal({ onClose, onSuccess }: Props) {
  const inputRef                    = useRef<HTMLInputElement>(null);
  const [file,          setFile]          = useState<File | null>(null);
  const [fileError,     setFileError]     = useState<string | null>(null);
  const [uploading,     setUploading]     = useState(false);
  const [result,        setResult]        = useState<BulkImportResult | null>(null);
  const [resultMessage, setResultMessage] = useState<string | null>(null);
  const [submitError,   setSubmitError]   = useState<string | null>(null);

  // GET /recruitment/candidates/bulk-import/sample/?format= — system_admin,
  // hr_admin, or hr only (backend-enforced; we just relay its 403 message).
  const [sampleDownloading, setSampleDownloading] = useState<SampleFormat | null>(null);
  const [sampleError,       setSampleError]       = useState<string | null>(null);

  async function handleDownloadSample(format: SampleFormat) {
    setSampleDownloading(format);
    setSampleError(null);
    const res = await downloadBlobFile(
      API.recruitment.bulkImportSample,
      { format },
      `candidate_import_sample.${format}`,
    );
    if (!res.success) setSampleError(res.message ?? "Failed to download sample file.");
    setSampleDownloading(null);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    setResult(null);
    setResultMessage(null);
    setSubmitError(null);
    if (!picked) {
      setFile(null);
      setFileError(null);
      return;
    }
    const validationError = validateFile(picked);
    setFile(validationError ? null : picked);
    setFileError(validationError);
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setSubmitError(null);
    setResult(null);
    setResultMessage(null);
    try {
      const formData = new FormData();
      formData.append("file", file, file.name);
      const res = await clientApi.post<{ success: boolean; message: string; data: BulkImportResult | null }>(
        API.recruitment.bulkImport,
        formData,
      );
      if (res.data.data) {
        setResult(res.data.data);
        setResultMessage(res.data.message);
        if (res.data.data.imported > 0) onSuccess();
      } else {
        setSubmitError(res.data.message || "No valid rows found.");
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Import failed. Please check your file and try again.";
      setSubmitError(msg);
    } finally {
      setUploading(false);
    }
  }

  function handleClose() {
    setFile(null);
    setFileError(null);
    setResult(null);
    setResultMessage(null);
    setSubmitError(null);
    onClose();
  }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && handleClose()}>
      <div className="modal" style={{ maxWidth: 520 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title"><i className="ti ti-file-upload" style={{ marginRight: 8 }} />Bulk Import Candidates</div>
          <button className="modal-close" onClick={handleClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body">
          {/* Instructions */}
          <div style={{ padding: "12px 14px", borderRadius: 8, background: "rgba(30,78,140,0.06)", border: "1px solid rgba(30,78,140,0.15)", marginBottom: 20, fontSize: 12, color: "var(--on-variant)", lineHeight: 1.6 }}>
            <div style={{ fontWeight: 600, color: "var(--primary)", marginBottom: 4, fontSize: 12 }}>
              <i className="ti ti-info-circle" style={{ marginRight: 5 }} />File Requirements
            </div>
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              <li>Accepted formats: <strong>.csv</strong>, <strong>.xlsx</strong> (max 5 MB)</li>
              <li>Required columns: <code style={{ background: "rgba(0,0,0,0.06)", padding: "0 4px", borderRadius: 3 }}>Name</code>, <code style={{ background: "rgba(0,0,0,0.06)", padding: "0 4px", borderRadius: 3 }}>Email</code>, <code style={{ background: "rgba(0,0,0,0.06)", padding: "0 4px", borderRadius: 3 }}>Position</code>, <code style={{ background: "rgba(0,0,0,0.06)", padding: "0 4px", borderRadius: 3 }}>Branch</code></li>
              <li>Optional columns: Phone, Interview Date, Interview Mode, Notes</li>
            </ul>
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => handleDownloadSample("csv")} disabled={!!sampleDownloading} suppressHydrationWarning>
                <i className="ti ti-download" /> {sampleDownloading === "csv" ? "Downloading…" : "Sample CSV"}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => handleDownloadSample("xlsx")} disabled={!!sampleDownloading} suppressHydrationWarning>
                <i className="ti ti-download" /> {sampleDownloading === "xlsx" ? "Downloading…" : "Sample XLSX"}
              </button>
            </div>
            {sampleError && (
              <div style={{ marginTop: 8, color: "var(--error)", fontSize: 11.5 }}>{sampleError}</div>
            )}
          </div>

          {/* Drop zone */}
          <div
            onClick={() => inputRef.current?.click()}
            style={{
              border: `2px dashed ${file ? "var(--primary)" : "var(--outline-v)"}`,
              borderRadius: 10, padding: "28px 20px", textAlign: "center",
              cursor: "pointer", background: file ? "rgba(30,78,140,0.04)" : "var(--bg-low)",
              transition: "border-color 0.15s, background 0.15s", marginBottom: 16,
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.xlsx"
              style={{ display: "none" }}
              onChange={handleFileChange}
            />
            <i className={`ti ${file ? "ti-file-check" : "ti-upload"}`} style={{ fontSize: 28, color: file ? "var(--primary)" : "var(--outline)", display: "block", marginBottom: 8 }} />
            {file ? (
              <>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--primary)" }}>{file.name}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 3 }}>
                  {(file.size / 1024).toFixed(1)} KB · Click to change
                </div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>Click to select file</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 3 }}>.csv · .xlsx</div>
              </>
            )}
          </div>

          {fileError && (
            <div className="alert alert-error" style={{ marginBottom: 12 }}>
              <i className="ti ti-alert-circle" />
              <span>{fileError}</span>
            </div>
          )}

          {submitError && (
            <div className="alert alert-error" style={{ marginBottom: 12 }}>
              <i className="ti ti-alert-circle" />
              <span>{submitError}</span>
            </div>
          )}

          {/* Result summary */}
          {result && (
            <div style={{ borderRadius: 8, border: "1px solid var(--outline-v)", overflow: "hidden" }}>
              <div className="alert alert-success" style={{ margin: 0, borderRadius: "8px 8px 0 0", border: "none" }}>
                <i className="ti ti-circle-check" />
                <span>{resultMessage}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", textAlign: "center" }}>
                {[
                  { label: "Imported", value: result.imported, color: "var(--success)" },
                  { label: "Failed",   value: result.failed,   color: result.failed > 0 ? "var(--error)" : "var(--on-variant)" },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ padding: "12px 8px", borderRight: "1px solid var(--outline-v)" }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>{label}</div>
                  </div>
                ))}
              </div>

              {result.errors.length > 0 && (
                <div style={{ borderTop: "1px solid var(--outline-v)", maxHeight: 200, overflowY: "auto" }}>
                  <table style={{ width: "100%", fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: "var(--bg-low)" }}>
                        <th style={{ textAlign: "left", padding: "6px 14px" }}>Row</th>
                        <th style={{ textAlign: "left", padding: "6px 14px" }}>Field</th>
                        <th style={{ textAlign: "left", padding: "6px 14px" }}>Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.errors.map((e, i) => (
                        <tr key={i} style={{ borderTop: "1px solid var(--outline-v)" }}>
                          <td style={{ padding: "7px 14px", color: "var(--on-variant)" }}>{e.row}</td>
                          <td style={{ padding: "7px 14px", color: "var(--on-variant)" }}>{e.field}</td>
                          <td style={{ padding: "7px 14px", color: "var(--error)" }}>{e.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={handleClose}>
            {result ? "Close" : "Cancel"}
          </button>
          {!result && (
            <button
              className="btn btn-filled"
              onClick={handleUpload}
              disabled={!file || uploading}
              suppressHydrationWarning
            >
              {uploading
                ? <><i className="ti ti-loader-2 spin" /> Uploading…</>
                : <><i className="ti ti-file-upload" /> Upload & Import</>
              }
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
