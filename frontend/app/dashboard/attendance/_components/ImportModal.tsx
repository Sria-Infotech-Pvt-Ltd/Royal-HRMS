"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import Modal from "@/components/Modal";
import type { ImportResult, ImportRowError } from "@/types/attendance";

type SampleFormat = "csv" | "xlsx";

interface Props {
  onClose:    () => void;
  onImported: (result: ImportResult) => void;
}

function downloadBase64Csv(base64: string, filename: string) {
  const link = document.createElement("a");
  link.href = `data:text/csv;base64,${base64}`;
  link.download = filename;
  link.click();
}

export default function ImportModal({ onClose, onImported }: Props) {
  const [file,      setFile]      = useState<File | null>(null);
  const [dragOver,  setDragOver]  = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error,     setError]     = useState<string | null>(null);
  const [result,    setResult]    = useState<ImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // GET /attendance/import/sample/?format= — requires attendance.create
  // (backend-enforced; we just relay whatever message it sends on 403).
  const [sampleDownloading, setSampleDownloading] = useState<SampleFormat | null>(null);
  const [sampleError,       setSampleError]       = useState<string | null>(null);

  async function handleDownloadSample(format: SampleFormat) {
    setSampleDownloading(format);
    setSampleError(null);
    const res = await downloadBlobFile(
      API.attendance.importSample,
      { format },
      `attendance_import_sample.${format}`,
    );
    if (!res.success) setSampleError(res.message ?? "Failed to download sample file.");
    setSampleDownloading(null);
  }

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

  const isPartial  = result?.status === "partial_success";
  const isSuccess  = result?.status === "success";
  const hasFailed  = (result?.failed ?? 0) > 0;
  const hasSkipped = (result?.skipped ?? 0) > 0;

  return (
    <Modal
      title={
        <>
          <i className="ti ti-upload" style={{ marginRight: 8, color: "var(--primary)" }} />
          Import Attendance
        </>
      }
      onClose={onClose}
      maxWidth={560}
      footer={
        !result ? (
          <>
            <button className="btn btn-ghost" onClick={onClose} disabled={uploading}>Cancel</button>
            <button className="btn btn-filled" onClick={handleUpload} disabled={uploading || !file}>
              {uploading
                ? <><i className="ti ti-loader-2" style={{ marginRight: 6 }} />Uploading…</>
                : <><i className="ti ti-upload" style={{ marginRight: 6 }} />Upload &amp; Process</>
              }
            </button>
          </>
        ) : (
          <>
            {hasFailed && !isSuccess && (
              <button className="btn btn-ghost" onClick={() => { setResult(null); setFile(null); }}>
                Import Another File
              </button>
            )}
            <button className="btn btn-filled" onClick={() => onImported(result)}>Done</button>
          </>
        )
      }
    >
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

              <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                <button className="btn btn-ghost btn-sm" onClick={() => handleDownloadSample("csv")} disabled={!!sampleDownloading} suppressHydrationWarning>
                  <i className="ti ti-download" /> {sampleDownloading === "csv" ? "Downloading…" : "Sample CSV"}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => handleDownloadSample("xlsx")} disabled={!!sampleDownloading} suppressHydrationWarning>
                  <i className="ti ti-download" /> {sampleDownloading === "xlsx" ? "Downloading…" : "Sample XLSX"}
                </button>
              </div>
              {sampleError && (
                <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> <span>{sampleError}</span></div>
              )}

              {error && (
                <div className="alert alert-error mb-16">
                  <i className="ti ti-alert-circle" /> <span>{error}</span>
                </div>
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
              {/* Summary banner */}
              <div className={`alert ${hasFailed ? (isPartial ? "alert-warn" : "alert-error") : "alert-success"} mb-16`}>
                <i className={`ti ${hasFailed ? (isPartial ? "ti-alert-triangle" : "ti-circle-x") : "ti-circle-check"}`} />
                <span>{result.message}</span>
              </div>

              {/* Stat tiles */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 20 }}>
                {[
                  { label: "Total",      value: result.total_records, color: "var(--primary)",    bg: "rgba(30,78,140,0.06)"  },
                  { label: "Successful", value: result.successful,    color: "var(--success)",    bg: "rgba(34,197,94,0.08)"  },
                  { label: "Failed",     value: result.failed,        color: result.failed  > 0 ? "var(--error)"  : "var(--on-variant)", bg: result.failed  > 0 ? "rgba(239,68,68,0.08)"  : "var(--bg-low)" },
                  { label: "Skipped",    value: result.skipped,       color: result.skipped > 0 ? "var(--warn)"   : "var(--on-variant)", bg: result.skipped > 0 ? "rgba(234,179,8,0.08)"  : "var(--bg-low)" },
                ].map(tile => (
                  <div key={tile.label} style={{
                    padding: "10px 8px", borderRadius: 8, textAlign: "center",
                    border: "1px solid var(--outline-v)", background: tile.bg,
                  }}>
                    <div style={{ fontSize: 20, fontWeight: 700, color: tile.color }}>{tile.value}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>{tile.label}</div>
                  </div>
                ))}
              </div>

              {/* Error table */}
              {hasFailed && result.errors.length > 0 && (
                <div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
                      <i className="ti ti-alert-circle" style={{ marginRight: 5, color: "var(--error)" }} />
                      {result.failed} Failed Row{result.failed !== 1 ? "s" : ""}
                    </div>
                    {result.error_report_csv && (
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => downloadBase64Csv(result.error_report_csv, "attendance_import_errors.csv")}
                        suppressHydrationWarning
                      >
                        <i className="ti ti-download" style={{ marginRight: 4 }} />
                        Download Error Report
                      </button>
                    )}
                  </div>

                  <div style={{ border: "1px solid var(--outline-v)", borderRadius: 8, overflow: "hidden", maxHeight: 260, overflowY: "auto" }}>
                    <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                      <thead>
                        <tr style={{ background: "var(--bg-low)", position: "sticky", top: 0 }}>
                          <th style={{ textAlign: "left", padding: "7px 12px", fontWeight: 600, color: "var(--on-variant)", whiteSpace: "nowrap" }}>Row</th>
                          <th style={{ textAlign: "left", padding: "7px 12px", fontWeight: 600, color: "var(--on-variant)", whiteSpace: "nowrap" }}>Employee</th>
                          <th style={{ textAlign: "left", padding: "7px 12px", fontWeight: 600, color: "var(--on-variant)", whiteSpace: "nowrap" }}>Date</th>
                          <th style={{ textAlign: "left", padding: "7px 12px", fontWeight: 600, color: "var(--on-variant)" }}>Reason</th>
                          <th style={{ textAlign: "left", padding: "7px 12px", fontWeight: 600, color: "var(--on-variant)" }}>Resolution</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.errors.map((e, i) => (
                          <tr key={i} style={{ borderTop: "1px solid var(--outline-v)" }}>
                            <td style={{ padding: "8px 12px", fontFamily: "Menlo, Consolas, monospace", color: "var(--on-variant)" }}>
                              {e.row}
                            </td>
                            <td style={{ padding: "8px 12px", color: "var(--on-bg)" }}>
                              {e.employee_name || e.employee_id || <span style={{ color: "var(--outline)", fontStyle: "italic" }}>—</span>}
                            </td>
                            <td style={{ padding: "8px 12px", color: "var(--on-variant)", whiteSpace: "nowrap" }}>
                              {e.attendance_date || <span style={{ color: "var(--outline)", fontStyle: "italic" }}>—</span>}
                            </td>
                            <td style={{ padding: "8px 12px", color: "var(--error)" }}>
                              {e.reason}
                            </td>
                            <td style={{ padding: "8px 12px", color: "var(--on-variant)" }}>
                              {e.resolution}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {(isSuccess || (!hasFailed && !hasSkipped)) && (
                <div style={{ textAlign: "center", padding: "12px 0 4px" }}>
                  <i className="ti ti-circle-check" style={{ fontSize: 32, color: "var(--success)", display: "block", marginBottom: 6 }} />
                  <div style={{ fontSize: 13, color: "var(--on-variant)" }}>All records imported successfully.</div>
                </div>
              )}
            </>
          )}
    </Modal>
  );
}
