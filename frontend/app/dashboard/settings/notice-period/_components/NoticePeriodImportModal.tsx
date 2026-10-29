"use client";

// Settings → Notice Period → Import (CSV / Excel). Same flow as Settings →
// Assets → Bulk Assign: preview first (nothing saved), then an explicit
// confirmation; the server checks every row again before saving. Employees
// are matched by Employee ID; a blank notice period leaves the row unchanged.

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import Modal from "@/components/Modal";
import { checkImportFile } from "@/lib/assetImport";
import {
  NOTICE_IMPORT_STATUS_LABEL, noticeChangeText,
  type NoticeImportRow, type NoticeImportStatus, type NoticeImportSummary,
} from "@/lib/noticePeriod";

interface ImportResponse { summary: NoticeImportSummary; rows: NoticeImportRow[] }

const STATUS_COLOR: Record<NoticeImportStatus, string> = {
  update:    "var(--success, #1a7f37)",
  updated:   "var(--success, #1a7f37)",
  no_change: "var(--on-variant)",
  skipped:   "#9a6700",
  error:     "var(--error)",
};

function apiMessage(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
}

function Rows({ rows }: { rows: NoticeImportRow[] }) {
  return (
    <div style={{ overflowX: "auto", maxHeight: 320, overflowY: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
      <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
        <thead>
          <tr><th>Row</th><th>Employee</th><th>Notice Period</th><th>Status</th><th>Details</th></tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.row}>
              <td>{r.row}</td>
              <td>{r.name ? `${r.name} (${r.employee_id})` : r.employee_id || "—"}</td>
              <td>{noticeChangeText(r)}</td>
              <td style={{ color: STATUS_COLOR[r.status], fontWeight: 600, whiteSpace: "nowrap" }}>{NOTICE_IMPORT_STATUS_LABEL[r.status]}</td>
              <td style={{ color: "var(--on-variant)" }}>{r.status === "error" || r.status === "skipped" ? r.message : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function NoticePeriodImportModal({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportResponse | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<ImportResponse | null>(null);
  const [busy, setBusy] = useState<"preview" | "save" | null>(null);
  const [sampleDl, setSampleDl] = useState<"csv" | "xlsx" | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function reset() {
    setFile(null); setPreview(null); setConfirming(false); setResult(null); setErrorMsg(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function pick(f: File | undefined) {
    setPreview(null); setConfirming(false); setResult(null); setErrorMsg(null);
    if (!f) return;
    const problem = checkImportFile(f);
    if (problem) { setErrorMsg(problem); setFile(null); return; }
    setFile(f);
  }

  async function sample(format: "csv" | "xlsx") {
    setSampleDl(format);
    const res = await downloadBlobFile(API.employees.noticePeriodImportSample, { format }, `notice_period_import_sample.${format}`);
    if (!res.success) setErrorMsg(res.message ?? "Failed to download the sample.");
    setSampleDl(null);
  }

  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(dryRun ? "preview" : "save");
    setErrorMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    if (dryRun) fd.append("dry_run", "true");
    try {
      const { data } = await clientApi.post(API.employees.noticePeriodImport, fd, { headers: { "Content-Type": undefined } });
      if (dryRun) {
        setPreview(data.data);
      } else {
        setResult(data.data); setPreview(null); setConfirming(false);
        if (data.data.summary.updated) onImported();
      }
    } catch (err) {
      setConfirming(false);
      setErrorMsg(apiMessage(err, dryRun ? "Could not check the file." : "Import failed."));
    } finally {
      setBusy(null);
    }
  }

  const toUpdate = preview?.summary.update ?? 0;

  return (
    <Modal
      title={<><i className="ti ti-file-import" style={{ marginRight: 8 }} />Import Notice Periods</>}
      onClose={onClose}
      closeDisabled={!!busy}
      size="lg"
      footer={
        result ? (
          <>
            <button className="btn btn-ghost" onClick={reset}>Import another file</button>
            <button className="btn btn-filled" onClick={onClose}>Done</button>
          </>
        ) : preview && confirming ? (
          <>
            <button className="btn btn-ghost" onClick={() => setConfirming(false)} disabled={!!busy}>Back</button>
            <button className="btn btn-filled" onClick={() => send(false)} disabled={!!busy}>
              {busy === "save" ? "Saving…" : `Yes, update ${toUpdate} employee(s)`}
            </button>
          </>
        ) : preview ? (
          <>
            <button className="btn btn-ghost" onClick={reset} disabled={!!busy}>Cancel</button>
            <button className="btn btn-filled" onClick={() => setConfirming(true)} disabled={!!busy || toUpdate === 0}>
              {`Update ${toUpdate} employee(s)…`}
            </button>
          </>
        ) : (
          <>
            <button className="btn btn-ghost" onClick={onClose} disabled={!!busy}>Cancel</button>
            <button className="btn btn-filled" onClick={() => send(true)} disabled={!file || !!busy}>
              {busy === "preview" ? "Checking…" : "Preview"}
            </button>
          </>
        )
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 14, fontSize: 13 }}>
        {!preview && !result && (
          <>
            <div style={{ color: "var(--on-variant)", lineHeight: 1.5 }}>
              Upload a CSV or Excel (.xlsx) file with columns <strong>Employee ID</strong> and{" "}
              <strong>Notice Period (days)</strong> — up to 1000 rows, 5 MB. Notice period is a whole number of
              days from 0 to 365. A blank notice period leaves that employee unchanged. Nothing is saved until you confirm.
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <button className="btn btn-ghost btn-sm" onClick={() => sample("csv")} disabled={!!sampleDl}>
                <i className="ti ti-download" /> {sampleDl === "csv" ? "Downloading…" : "Download Sample CSV"}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => sample("xlsx")} disabled={!!sampleDl}>
                <i className="ti ti-download" /> {sampleDl === "xlsx" ? "Downloading…" : "Download Sample Excel"}
              </button>
              <label className="btn btn-ghost btn-sm" style={{ cursor: busy ? "default" : "pointer" }}>
                <i className="ti ti-upload" /> {file ? "Choose another file" : "Choose CSV / Excel file"}
                <input ref={inputRef} type="file" accept=".csv,.xlsx" hidden disabled={!!busy}
                  onChange={e => pick(e.target.files?.[0])} />
              </label>
              {file && <span><i className="ti ti-file" /> {file.name}</span>}
            </div>
          </>
        )}

        {errorMsg && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{errorMsg}</div></div>}

        {preview && (
          <>
            <div className={`alert ${preview.summary.error ? "alert-warn" : "alert-info"}`}>
              <i className="ti ti-list-check" />
              <div>
                Preview (nothing saved yet): <strong>{preview.summary.update}</strong> to update,{" "}
                <strong>{preview.summary.no_change}</strong> no change, <strong>{preview.summary.skipped}</strong> skipped,{" "}
                <strong>{preview.summary.error}</strong> with errors. Only &ldquo;Will update&rdquo; rows are saved.
              </div>
            </div>
            {confirming && (
              <div className="alert alert-warn">
                <i className="ti ti-alert-triangle" />
                <div>
                  Update the notice period of <strong>{toUpdate}</strong> employee(s)? Every row is checked again before
                  saving; anything that changed since this preview is reported instead of saved.
                </div>
              </div>
            )}
            <Rows rows={preview.rows} />
          </>
        )}

        {result && (
          <>
            <div className={`alert ${result.summary.error ? "alert-warn" : "alert-success"}`}>
              <i className={`ti ${result.summary.error ? "ti-alert-triangle" : "ti-circle-check"}`} />
              <div>
                Finished: <strong>{result.summary.updated ?? 0}</strong> updated, <strong>{result.summary.no_change}</strong> no change,{" "}
                <strong>{result.summary.skipped}</strong> skipped, <strong>{result.summary.error}</strong> with errors
                (of {result.summary.total} rows).
              </div>
            </div>
            <Rows rows={result.rows} />
          </>
        )}
      </div>
    </Modal>
  );
}
