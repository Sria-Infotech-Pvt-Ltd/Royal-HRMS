"use client";

import { useRef, useState } from "react";
import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import { formatDate } from "@/lib/formatDate";
import Modal from "@/components/Modal";
import type {
  ImportPreviewRow,
  ImportValidateResult,
  OpeningBalanceImportResult,
} from "@/types/leave";

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".csv", ".xlsx"];

type SampleFormat = "csv" | "xlsx";
type Phase = "upload" | "preview" | "result";

interface Props {
  onClose:   () => void;
  onSuccess: () => void;
}

function validateFile(file: File): string | null {
  const ok = ACCEPTED_EXTENSIONS.some(ext => file.name.toLowerCase().endsWith(ext));
  if (!ok) return tr("Unsupported file type. Please upload a .csv or .xlsx file.");
  if (file.size > MAX_FILE_SIZE_BYTES) return tr("File is too large. Maximum allowed size is 5 MB.");
  return null;
}

function downloadErrorReportCsv(csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "leave_import_errors.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function fmtDate(d: string | null) {
  if (!d) return "—";
  return formatDate(d);
}

export default function OpeningBalanceImportModal({ onClose, onSuccess }: Props) {
  const t = useT();
  const inputRef = useRef<HTMLInputElement>(null);

  const [phase,         setPhase]         = useState<Phase>("upload");
  const [file,          setFile]          = useState<File | null>(null);
  const [fileError,     setFileError]     = useState<string | null>(null);
  const [validating,    setValidating]    = useState(false);
  const [importing,     setImporting]     = useState(false);
  const [apiError,      setApiError]      = useState<string | null>(null);
  const [preview,       setPreview]       = useState<ImportValidateResult | null>(null);
  const [result,        setResult]        = useState<OpeningBalanceImportResult | null>(null);
  const [sampleDl,      setSampleDl]      = useState<SampleFormat | null>(null);
  const [sampleError,   setSampleError]   = useState<string | null>(null);

  async function handleDownloadSample(format: SampleFormat) {
    setSampleDl(format);
    setSampleError(null);
    const res = await downloadBlobFile(
      API.leave.balanceImportSample,
      { format },
      `leave_opening_balance_sample.${format}`,
    );
    if (!res.success) setSampleError(res.message ?? t("Failed to download sample."));
    setSampleDl(null);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    setPreview(null);
    setResult(null);
    setApiError(null);
    setPhase("upload");
    if (!picked) { setFile(null); setFileError(null); return; }
    const err = validateFile(picked);
    setFile(err ? null : picked);
    setFileError(err);
  }

  async function handleValidate() {
    if (!file) return;
    setValidating(true);
    setApiError(null);
    try {
      const fd = new FormData();
      fd.append("file", file, file.name);
      const res = await clientApi.post<{ status: string; data: ImportValidateResult }>(
        API.leave.balanceImportValidate,
        fd,
      );
      setPreview(res.data.data);
      setPhase("preview");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? t("Validation failed. Please check your file.");
      setApiError(msg);
    } finally {
      setValidating(false);
    }
  }

  async function handleImport() {
    if (!file || !preview) return;
    setImporting(true);
    setApiError(null);
    try {
      const fd = new FormData();
      fd.append("file", file, file.name);
      const res = await clientApi.post<{ status: string; data: OpeningBalanceImportResult }>(
        API.leave.balanceImport,
        fd,
      );
      setResult(res.data.data);
      setPhase("result");
      if (res.data.data.successful > 0) onSuccess();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? t("Import failed. Please try again.");
      setApiError(msg);
    } finally {
      setImporting(false);
    }
  }

  function handleClose() {
    setFile(null); setFileError(null); setPreview(null);
    setResult(null); setApiError(null); setPhase("upload");
    onClose();
  }

  const validCount = preview?.valid_rows ?? 0;

  return (
    <Modal
      title={<><i className="ti ti-file-upload mr-2" />{t("Import Leave Balances & History")}</>}
      onClose={handleClose}
      size="lg"
      footer={
        <>
          <button className="btn btn-ghost" onClick={handleClose}>
            {phase === "result" ? t("Close") : t("Cancel")}
          </button>

          {phase === "upload" && (
            <button className="btn btn-filled" onClick={handleValidate} disabled={!file || validating} suppressHydrationWarning>
              {validating
                ? <><i className="ti ti-loader-2 spin" /> {t("Validating…")}</>
                : <><i className="ti ti-search" /> {t("Validate File")}</>}
            </button>
          )}

          {phase === "preview" && (
            <>
              <button className="btn btn-ghost" onClick={() => { setPhase("upload"); setPreview(null); setApiError(null); }}>
                <i className="ti ti-arrow-left" /> {t("Change File")}
              </button>
              <button
                className="btn btn-filled"
                onClick={handleImport}
                disabled={validCount === 0 || importing}
                suppressHydrationWarning
              >
                {importing
                  ? <><i className="ti ti-loader-2 spin" /> {t("Importing…")}</>
                  : <><i className="ti ti-file-upload" /> {validCount === 1 ? t("Import {count} valid row", { count: validCount }) : t("Import {count} valid rows", { count: validCount })}</>}
              </button>
            </>
          )}
        </>
      }
    >

          {/* ── Phase: upload ── */}
          {phase === "upload" && (
            <>
              <div className="alert alert-info mb-5">
                <i className="ti ti-info-circle" />
                <div>
                  <div className="font-semibold mb-1">{t("One-Time Historical Migration")}</div>
                  <p className="mb-2 text-sm">
                    {t("Use this to onboard existing employees or migrate from another HRMS. Each row is either a")} <strong>{t("Balance row")}</strong> {t("(annual totals) or a")} <strong>{t("History row")}</strong> {t("(individual leave dates). Leave the unused columns blank for each row type.")}
                  </p>
                  <ul className="list-disc pl-4 text-sm mb-0">
                    <li>{t("Accepted:")} <strong>.csv</strong>, <strong>.xlsx</strong> {t("(max 5 MB)")}</li>
                    <li><strong>{t("Balance columns:")}</strong> {t("Opening Balance, Leave Allocated, Leave Availed, Carry Forward Days")}</li>
                    <li><strong>{t("History columns:")}</strong> {t("From Date, To Date, Total Days (DD-Mon-YYYY or DD/MM/YYYY)")}</li>
                    <li>{t("Required on all rows: Employee ID, Leave Type, Financial Year")}</li>
                    <li>{t("All leave dates before today are auto-approved")}</li>
                    <li>{t("Duplicate employee/year balances and overlapping dates are skipped")}</li>
                  </ul>
                  <div className="flex gap-2 mt-2.5">
                    <button className="btn btn-ghost btn-sm" onClick={() => handleDownloadSample("csv")} disabled={!!sampleDl} suppressHydrationWarning>
                      <i className="ti ti-download" /> {sampleDl === "csv" ? t("Downloading…") : t("Sample CSV")}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => handleDownloadSample("xlsx")} disabled={!!sampleDl} suppressHydrationWarning>
                      <i className="ti ti-download" /> {sampleDl === "xlsx" ? t("Downloading…") : t("Sample XLSX")}
                    </button>
                  </div>
                  {sampleError && <div className="text-error text-xs mt-2">{sampleError}</div>}
                </div>
              </div>

              <div
                className={`upload-zone mb-4${file ? " upload-zone--active" : ""}`}
                onClick={() => inputRef.current?.click()}
              >
                <input ref={inputRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={handleFileChange} />
                <i className={`ti ${file ? "ti-file-check" : "ti-upload"}`} />
                <p className="font-semibold">{file ? file.name : t("Click to select file")}</p>
                <small>{file ? t("{size} KB · Click to change", { size: (file.size / 1024).toFixed(1) }) : ".csv · .xlsx"}</small>
              </div>

              {fileError  && <div className="alert alert-error mb-3"><i className="ti ti-alert-circle" /><span>{fileError}</span></div>}
              {apiError   && <div className="alert alert-error mb-3"><i className="ti ti-alert-circle" /><span>{apiError}</span></div>}
            </>
          )}

          {/* ── Phase: preview ── */}
          {phase === "preview" && preview && (
            <>
              <div className={`alert mb-4 ${preview.error_rows > 0 ? "alert-warn" : "alert-success"}`}>
                <i className={`ti ${preview.error_rows > 0 ? "ti-alert-triangle" : "ti-circle-check"}`} />
                <div>
                  <strong>{t("{valid} of {total} rows ready to import", { valid: validCount, total: preview.total_rows })}</strong>
                  {preview.error_rows > 0 && <span className="ml-2 text-sm">({t("{count} rows have errors and will be skipped", { count: preview.error_rows })})</span>}
                  <div className="text-sm mt-0.5">
                    {preview.balance_rows === 1 ? t("{count} balance row", { count: preview.balance_rows }) : t("{count} balance rows", { count: preview.balance_rows })} &nbsp;·&nbsp;
                    {preview.history_rows === 1 ? t("{count} history row", { count: preview.history_rows }) : t("{count} history rows", { count: preview.history_rows })}
                  </div>
                </div>
              </div>

              {apiError && <div className="alert alert-error mb-3"><i className="ti ti-alert-circle" /><span>{apiError}</span></div>}

              <div className="table-wrap max-h-72 overflow-y-auto rounded-lg border border-[var(--outline-v)]">
                <table>
                  <thead>
                    <tr>
                      <th style={{ width: 48 }}>{t("Row")}</th>
                      <th style={{ width: 80 }}>{t("Type")}</th>
                      <th>{t("Employee ID")}</th>
                      <th>{t("Leave Type")}</th>
                      <th>{t("FY / From Date")}</th>
                      <th>{t("To Date")}</th>
                      <th style={{ width: 48 }}>{t("Days")}</th>
                      <th>{t("Status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.preview.map((row: ImportPreviewRow) => (
                      <tr key={row.row} style={{ opacity: row.valid ? 1 : 0.7 }}>
                        <td className="text-muted">{row.row}</td>
                        <td>
                          <span className={`badge ${row.row_type === "history" ? "badge-info" : "badge-primary"}`} style={{ fontSize: 10 }}>
                            {row.row_type}
                          </span>
                        </td>
                        <td>{row.employee_id || "—"}</td>
                        <td>{row.leave_type || "—"}</td>
                        <td>{row.row_type === "history" ? fmtDate(row.from_date) : (row.financial_year || "—")}</td>
                        <td>{row.row_type === "history" ? fmtDate(row.to_date) : "—"}</td>
                        <td>{row.days ?? "—"}</td>
                        <td>
                          {row.valid
                            ? <span className="badge badge-success" style={{ fontSize: 10 }}>{t("Ready")}</span>
                            : <span className="text-error text-xs">{row.error}</span>
                          }
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {/* ── Phase: result ── */}
          {phase === "result" && result && (
            <>
              <div className="stats-grid mb-4">
                <div className="stat-card">
                  <div className="stat-label">{t("Total Rows")}</div>
                  <div className="stat-value">{result.total_records}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">{t("Balances")}</div>
                  <div className="stat-value text-success">{result.balances_created}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">{t("History")}</div>
                  <div className="stat-value text-success">{result.history_imported}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">{t("Skipped")}</div>
                  <div className={`stat-value${result.skipped > 0 ? " text-warn" : " text-muted"}`}>{result.skipped}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">{t("Failed")}</div>
                  <div className={`stat-value${result.failed > 0 ? " text-error" : " text-muted"}`}>{result.failed}</div>
                </div>
              </div>

              {result.errors.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="text-xs font-semibold">
                      {t("Errors")} {result.errors.length >= 100 && <span className="font-normal text-muted">{t("(showing first 100 — download for full report)")}</span>}
                    </div>
                    {result.error_report_csv && (
                      <button className="btn btn-ghost btn-sm" onClick={() => downloadErrorReportCsv(result.error_report_csv as string)} suppressHydrationWarning>
                        <i className="ti ti-download" /> {t("Download Error Report")}
                      </button>
                    )}
                  </div>
                  <div className="table-wrap max-h-56 overflow-y-auto rounded-lg border border-[var(--outline-v)]">
                    <table>
                      <thead>
                        <tr>
                          <th>{t("Row")}</th><th>{t("Employee ID")}</th><th>{t("Leave Type")}</th><th>{t("FY / From Date")}</th><th>{t("Reason")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.errors.map((e, i) => (
                          <tr key={i}>
                            <td className="text-muted">{e.row}</td>
                            <td className="text-muted">{e.employee_id}</td>
                            <td className="text-muted">{e.leave_type}</td>
                            <td className="text-muted">{e.from_date ?? e.financial_year}</td>
                            <td className="text-error">{e.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}

    </Modal>
  );
}
