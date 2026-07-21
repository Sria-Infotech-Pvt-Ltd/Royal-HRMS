"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { EmployeeBulkImportError, EmployeeBulkImportResult } from "@/types/employeeBulkImport";

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".csv", ".xlsx"];

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

function csvCell(value: string | number): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function downloadErrorReport(errors: EmployeeBulkImportError[]) {
  const rows = [
    ["Row", "Email", "Field", "Error"],
    ...errors.map(e => [e.row, e.identifier, e.field, e.message]),
  ];
  const csvContent = rows.map(row => row.map(csvCell).join(",")).join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "error_report.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export default function BulkImportModal({ onClose, onSuccess }: Props) {
  const inputRef                  = useRef<HTMLInputElement>(null);
  const [file,        setFile]        = useState<File | null>(null);
  const [fileError,   setFileError]   = useState<string | null>(null);
  const [uploading,   setUploading]   = useState(false);
  const [result,      setResult]      = useState<EmployeeBulkImportResult | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    setResult(null);
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
    try {
      const formData = new FormData();
      formData.append("file", file, file.name);
      const res = await clientApi.post<{ status: string; message: string; data: EmployeeBulkImportResult | null }>(
        API.employees.bulkImport,
        formData,
      );
      if (res.data.data) {
        setResult(res.data.data);
        if (res.data.data.created > 0) onSuccess();
      } else {
        setSubmitError(res.data.message || "Import failed. Please check your file and try again.");
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
    setSubmitError(null);
    onClose();
  }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && handleClose()}>
      <div className="modal" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title"><i className="ti ti-file-upload" style={{ marginRight: 8 }} />Bulk Import Employees</div>
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
              <li>Required columns: First Name, Last Name, Work Email, Role, Department, Designation, Branch, Date of Joining</li>
              <li>Optional columns: Phone, Employee Type, Gender, DOB, Blood Group, Address</li>
            </ul>
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
            <div>
              <div style={{ borderRadius: 8, border: "1px solid var(--outline-v)", overflow: "hidden", marginBottom: 16 }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", textAlign: "center" }}>
                  <div style={{ padding: "12px 8px", borderRight: "1px solid var(--outline-v)", background: "rgba(34,197,94,0.08)" }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: "var(--success)" }}>{result.created}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>Created</div>
                  </div>
                  <div style={{ padding: "12px 8px", borderRight: "1px solid var(--outline-v)", background: result.skipped > 0 ? "rgba(234,179,8,0.1)" : undefined }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: result.skipped > 0 ? "var(--warn)" : "var(--on-variant)" }}>{result.skipped}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>Skipped</div>
                  </div>
                  <div style={{ padding: "12px 8px", background: result.failed > 0 ? "rgba(239,68,68,0.08)" : undefined }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: result.failed > 0 ? "var(--error)" : "var(--on-variant)" }}>{result.failed}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>Failed</div>
                  </div>
                </div>
                <div style={{ padding: "8px 14px", fontSize: 11, color: "var(--on-variant)", borderTop: "1px solid var(--outline-v)" }}>
                  {result.total_rows} row{result.total_rows === 1 ? "" : "s"} processed
                </div>
              </div>

              {result.skipped_rows.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--on-bg)", marginBottom: 6 }}>Skipped Rows</div>
                  <div style={{ borderRadius: 8, border: "1px solid var(--outline-v)", maxHeight: 160, overflowY: "auto" }}>
                    <table style={{ width: "100%", fontSize: 12 }}>
                      <thead>
                        <tr style={{ background: "var(--bg-low)" }}>
                          <th style={{ textAlign: "left", padding: "6px 14px" }}>Row</th>
                          <th style={{ textAlign: "left", padding: "6px 14px" }}>Email</th>
                          <th style={{ textAlign: "left", padding: "6px 14px" }}>Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.skipped_rows.map((s, i) => (
                          <tr key={i} style={{ borderTop: "1px solid var(--outline-v)" }}>
                            <td style={{ padding: "7px 14px", color: "var(--on-variant)" }}>{s.row}</td>
                            <td style={{ padding: "7px 14px", color: "var(--on-variant)" }}>{s.identifier}</td>
                            <td style={{ padding: "7px 14px", color: "var(--warn)" }}>{s.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {result.errors.length > 0 && (
                <div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--on-bg)" }}>Errors</div>
                    <button className="btn btn-ghost btn-sm" onClick={() => downloadErrorReport(result.errors)} suppressHydrationWarning>
                      <i className="ti ti-download" /> Download Error Report
                    </button>
                  </div>
                  <div style={{ borderRadius: 8, border: "1px solid var(--outline-v)", maxHeight: 200, overflowY: "auto" }}>
                    <table style={{ width: "100%", fontSize: 12 }}>
                      <thead>
                        <tr style={{ background: "var(--bg-low)" }}>
                          <th style={{ textAlign: "left", padding: "6px 14px" }}>Row</th>
                          <th style={{ textAlign: "left", padding: "6px 14px" }}>Email</th>
                          <th style={{ textAlign: "left", padding: "6px 14px" }}>Field</th>
                          <th style={{ textAlign: "left", padding: "6px 14px" }}>Error Message</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.errors.map((e, i) => (
                          <tr key={i} style={{ borderTop: "1px solid var(--outline-v)" }}>
                            <td style={{ padding: "7px 14px", color: "var(--on-variant)" }}>{e.row}</td>
                            <td style={{ padding: "7px 14px", color: "var(--on-variant)" }}>{e.identifier}</td>
                            <td style={{ padding: "7px 14px", color: "var(--on-variant)" }}>{e.field}</td>
                            <td style={{ padding: "7px 14px", color: "var(--error)" }}>{e.message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
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
