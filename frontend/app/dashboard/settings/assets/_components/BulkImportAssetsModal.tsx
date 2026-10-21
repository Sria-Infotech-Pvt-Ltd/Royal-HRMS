"use client";

// Settings → Assets → Bulk Import (CSV / Excel). Preview first (nothing is
// saved), then confirm; every row is validated on the server by the same
// rules as Add Asset. Rows already in the system are reported as duplicates.

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import Modal from "@/components/Modal";
import {
  ASSET_IMPORT_COLUMNS, checkImportFile, decodeReport, errorText,
  type AssetImportPreview, type AssetImportResult, type AssetImportRow, type ImportRowStatus,
} from "@/lib/assetImport";

const STATUS: Record<ImportRowStatus, { label: string; color: string }> = {
  ready:     { label: "Ready",     color: "var(--success, #1a7f37)" },
  created:   { label: "Created",   color: "var(--success, #1a7f37)" },
  duplicate: { label: "Duplicate", color: "#9a6700" },
  error:     { label: "Error",     color: "var(--error)" },
};

function apiMessage(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
}

function Rows({ rows }: { rows: AssetImportRow[] }) {
  return (
    <div style={{ overflowX: "auto", maxHeight: 320, overflowY: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
      <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
        <thead>
          <tr><th>Row</th><th>Asset Tag</th><th>Name</th><th>Branch</th><th>Status</th><th>Details</th></tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.row}>
              <td>{r.row}</td>
              <td>{r.asset_tag || "—"}</td>
              <td>{r.asset_name || "—"}</td>
              <td>{r.branch || "—"}</td>
              <td style={{ color: STATUS[r.status].color, fontWeight: 600 }}>{STATUS[r.status].label}</td>
              <td style={{ color: "var(--on-variant)" }}>{errorText(r.errors)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BulkImportAssetsModal({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<AssetImportPreview | null>(null);
  const [result, setResult] = useState<AssetImportResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "import" | null>(null);
  const [sampleDl, setSampleDl] = useState<"csv" | "xlsx" | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function pick(f: File | undefined) {
    setPreview(null); setResult(null); setErrorMsg(null);
    if (!f) return;
    const problem = checkImportFile(f);
    if (problem) { setErrorMsg(problem); setFile(null); return; }
    setFile(f);
  }

  async function sample(format: "csv" | "xlsx") {
    setSampleDl(format);
    const res = await downloadBlobFile(API.assets.importSample, { format }, `asset_import_sample.${format}`);
    if (!res.success) setErrorMsg(res.message ?? "Failed to download the sample.");
    setSampleDl(null);
  }

  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(dryRun ? "preview" : "import");
    setErrorMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    if (dryRun) fd.append("dry_run", "true");
    try {
      const { data } = await clientApi.post(API.assets.import, fd, { headers: { "Content-Type": undefined } });
      if (dryRun) setPreview(data.data);
      else { setResult(data.data); setPreview(null); if (data.data.summary.created) onImported(); }
    } catch (err) {
      setErrorMsg(apiMessage(err, dryRun ? "Could not check the file." : "Import failed."));
    } finally {
      setBusy(null);
    }
  }

  function downloadReport(b64: string) {
    const url = URL.createObjectURL(new Blob([decodeReport(b64)], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "asset_import_errors.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function reset() {
    setFile(null); setPreview(null); setResult(null); setErrorMsg(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  const ready = preview?.counts.ready ?? 0;
  const report = result?.error_report_csv ?? preview?.error_report_csv ?? null;

  return (
    <Modal
      title={<><i className="ti ti-file-upload" style={{ marginRight: 8 }} />Bulk Import Assets</>}
      onClose={onClose}
      closeDisabled={!!busy}
      size="lg"
      footer={
        <>
          {report && (
            <button className="btn btn-ghost" onClick={() => downloadReport(report)} disabled={!!busy}>
              <i className="ti ti-download" /> Download error report
            </button>
          )}
          {result ? (
            <>
              <button className="btn btn-ghost" onClick={reset}>Import another file</button>
              <button className="btn btn-filled" onClick={onClose}>Done</button>
            </>
          ) : preview ? (
            <>
              <button className="btn btn-ghost" onClick={reset} disabled={!!busy}>Cancel</button>
              <button className="btn btn-filled" onClick={() => send(false)} disabled={!!busy || ready === 0}>
                {busy === "import" ? "Importing…" : `Import ${ready} asset(s)`}
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-ghost" onClick={onClose} disabled={!!busy}>Cancel</button>
              <button className="btn btn-filled" onClick={() => send(true)} disabled={!file || !!busy}>
                {busy === "preview" ? "Checking…" : "Preview"}
              </button>
            </>
          )}
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 14, fontSize: 13 }}>
        {!preview && !result && (
          <>
            <div style={{ color: "var(--on-variant)", lineHeight: 1.5 }}>
              Upload a CSV or Excel (.xlsx) file with one asset per row (up to 1000 rows, 5 MB). Each row is checked
              with the same rules as Add Asset; nothing is saved until you confirm. New assets start as Available.
            </div>
            <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
              <strong>Required columns:</strong> {ASSET_IMPORT_COLUMNS.filter(c => c.required).map(c => c.header).join(", ")}.{" "}
              <strong>Optional:</strong> {ASSET_IMPORT_COLUMNS.filter(c => !c.required).map(c => c.header).join(", ")}.
              Branch is a branch code or name; dates as YYYY-MM-DD.
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
            <div className={`alert ${preview.counts.error ? "alert-warn" : "alert-info"}`}>
              <i className="ti ti-list-check" />
              <div>
                Preview (nothing saved yet): <strong>{preview.counts.ready}</strong> ready,{" "}
                <strong>{preview.counts.duplicate}</strong> duplicate, <strong>{preview.counts.error}</strong> with errors.
                Only ready rows are imported.
              </div>
            </div>
            <Rows rows={preview.rows} />
          </>
        )}

        {result && (
          <>
            <div className={`alert ${result.summary.failed ? "alert-warn" : "alert-success"}`}>
              <i className={`ti ${result.summary.failed ? "ti-alert-triangle" : "ti-circle-check"}`} />
              <div>
                Import finished: <strong>{result.summary.created}</strong> created,{" "}
                <strong>{result.summary.duplicate}</strong> duplicate, <strong>{result.summary.failed}</strong> failed,{" "}
                <strong>{result.summary.skipped}</strong> skipped (of {result.summary.total} rows).
              </div>
            </div>
            <Rows rows={result.rows} />
          </>
        )}
      </div>
    </Modal>
  );
}
