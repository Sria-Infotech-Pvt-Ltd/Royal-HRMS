"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import type { OpeningBalanceImportResult } from "@/types/leave";

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

// error_report_csv arrives as a raw CSV string from the backend — not rows to
// build, just bytes to save — so this bypasses lib/csv.ts's buildCsv/downloadCsv.
function downloadErrorReportCsv(csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "leave_opening_balance_import_errors.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export default function OpeningBalanceImportModal({ onClose, onSuccess }: Props) {
  const inputRef                = useRef<HTMLInputElement>(null);
  const [file,        setFile]        = useState<File | null>(null);
  const [fileError,   setFileError]   = useState<string | null>(null);
  const [uploading,   setUploading]   = useState(false);
  const [result,      setResult]      = useState<OpeningBalanceImportResult | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [sampleDownloading, setSampleDownloading] = useState<SampleFormat | null>(null);
  const [sampleError,       setSampleError]       = useState<string | null>(null);

  async function handleDownloadSample(format: SampleFormat) {
    setSampleDownloading(format);
    setSampleError(null);
    const res = await downloadBlobFile(
      API.leave.balanceImportSample,
      { format },
      `leave_opening_balance_sample.${format}`,
    );
    if (!res.success) setSampleError(res.message ?? "Failed to download sample file.");
    setSampleDownloading(null);
  }

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
      const res = await clientApi.post<{ status: string; message: string; data: OpeningBalanceImportResult }>(
        API.leave.balanceImport,
        formData,
      );
      setResult(res.data.data);
      if (res.data.data.successful > 0) onSuccess();
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
      <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title"><i className="ti ti-file-upload mr-2" />Import Opening Leave Balances</div>
          <button className="modal-close" onClick={handleClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body">
          {/* Instructions */}
          <div className="alert alert-info mb-5">
            <i className="ti ti-info-circle" />
            <div>
              <div className="font-semibold mb-1">One-Time Historical Migration</div>
              <p className="mb-2">
                Use this only when onboarding an existing company or migrating off another HRMS. Once opening balances
                are recorded, all further leave usage, crediting, and carry-forward is handled automatically by the
                Leave module — re-running this import will skip any employee/leave-type/year combination already on file.
              </p>
              <ul className="list-disc pl-4 mb-0">
                <li>Accepted formats: <strong>.csv</strong>, <strong>.xlsx</strong> (max 5 MB)</li>
                <li>Columns: Employee ID, Leave Type, Financial Year, Opening Balance, Leave Allocated, Leave Availed, Leave Balance, Carry Forward Days, Remarks</li>
              </ul>
              <div className="flex gap-2 mt-2.5">
                <button className="btn btn-ghost btn-sm" onClick={() => handleDownloadSample("csv")} disabled={!!sampleDownloading} suppressHydrationWarning>
                  <i className="ti ti-download" /> {sampleDownloading === "csv" ? "Downloading…" : "Sample CSV"}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => handleDownloadSample("xlsx")} disabled={!!sampleDownloading} suppressHydrationWarning>
                  <i className="ti ti-download" /> {sampleDownloading === "xlsx" ? "Downloading…" : "Sample XLSX"}
                </button>
              </div>
              {sampleError && <div className="text-error text-xs mt-2">{sampleError}</div>}
            </div>
          </div>

          {/* Drop zone */}
          <div
            className={`upload-zone mb-4${file ? " upload-zone--active" : ""}`}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.xlsx"
              className="hidden"
              onChange={handleFileChange}
            />
            <i className={`ti ${file ? "ti-file-check" : "ti-upload"}`} />
            <p className="font-semibold">
              {file ? file.name : "Click to select file"}
            </p>
            <small>{file ? `${(file.size / 1024).toFixed(1)} KB · Click to change` : ".csv · .xlsx"}</small>
          </div>

          {fileError && (
            <div className="alert alert-error mb-3">
              <i className="ti ti-alert-circle" />
              <span>{fileError}</span>
            </div>
          )}

          {submitError && (
            <div className="alert alert-error mb-3">
              <i className="ti ti-alert-circle" />
              <span>{submitError}</span>
            </div>
          )}

          {/* Result summary */}
          {result && (
            <div>
              <div className="stats-grid mb-4">
                <div className="stat-card">
                  <div className="stat-label">Total Rows</div>
                  <div className="stat-value">{result.total_records}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Successful</div>
                  <div className="stat-value text-success">{result.successful}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Skipped</div>
                  <div className={`stat-value${result.skipped > 0 ? " text-warn" : " text-muted"}`}>{result.skipped}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Failed</div>
                  <div className={`stat-value${result.failed > 0 ? " text-error" : " text-muted"}`}>{result.failed}</div>
                </div>
              </div>

              {result.errors.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="text-xs font-semibold">
                      Errors {result.errors.length >= 100 && <span className="font-normal text-muted">(showing first 100 — download the full report)</span>}
                    </div>
                    {result.error_report_csv && (
                      <button className="btn btn-ghost btn-sm" onClick={() => downloadErrorReportCsv(result.error_report_csv as string)} suppressHydrationWarning>
                        <i className="ti ti-download" /> Download Error Report
                      </button>
                    )}
                  </div>
                  <div className="table-wrap max-h-56 overflow-y-auto rounded-lg border border-[var(--outline-v)]">
                    <table>
                      <thead>
                        <tr>
                          <th>Row</th>
                          <th>Employee ID</th>
                          <th>Leave Type</th>
                          <th>Financial Year</th>
                          <th>Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.errors.map((e, i) => (
                          <tr key={i}>
                            <td className="text-muted">{e.row}</td>
                            <td className="text-muted">{e.employee_id}</td>
                            <td className="text-muted">{e.leave_type}</td>
                            <td className="text-muted">{e.financial_year}</td>
                            <td className="text-error">{e.reason}</td>
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
                ? <><i className="ti ti-loader-2 spin" /> Importing…</>
                : <><i className="ti ti-file-upload" /> Upload &amp; Import</>
              }
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
