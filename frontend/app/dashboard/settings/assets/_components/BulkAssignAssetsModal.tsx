"use client";

// Settings → Assets → Bulk Assign (CSV / Excel). Preview first (nothing is
// assigned), then an explicit confirmation; every row is validated on the
// server with the same rules as Assign Asset. Assets that are already
// assigned are reported, never reassigned.

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import Modal from "@/components/Modal";
import { checkImportFile, decodeReport, errorText } from "@/lib/assetImport";
import {
  ASSET_ASSIGN_COLUMNS, ASSIGN_STATUS_LABEL, mappingText,
  type AssetAssignPreview, type AssetAssignResult, type AssetAssignRow, type AssignRowStatus,
} from "@/lib/assetAssignImport";

const STATUS_COLOR: Record<AssignRowStatus, string> = {
  ready:            "var(--success, #1a7f37)",
  assigned:         "var(--success, #1a7f37)",
  already_assigned: "#9a6700",
  error:            "var(--error)",
};

function apiMessage(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
}

function Rows({ rows }: { rows: AssetAssignRow[] }) {
  return (
    <div style={{ overflowX: "auto", maxHeight: 320, overflowY: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
      <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
        <thead>
          <tr><th>Row</th><th>Asset</th><th>Employee</th><th>Status</th><th>Details</th></tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const m = mappingText(r);
            return (
              <tr key={r.row}>
                <td>{r.row}</td>
                <td>{m.asset}</td>
                <td>{m.employee}</td>
                <td style={{ color: STATUS_COLOR[r.status], fontWeight: 600, whiteSpace: "nowrap" }}>{ASSIGN_STATUS_LABEL[r.status]}</td>
                <td style={{ color: "var(--on-variant)" }}>{errorText(r.errors)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function BulkAssignAssetsModal({ onClose, onAssigned }: { onClose: () => void; onAssigned: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<AssetAssignPreview | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<AssetAssignResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "assign" | null>(null);
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
    const res = await downloadBlobFile(API.assets.assignImportSample, { format }, `asset_assignment_sample.${format}`);
    if (!res.success) setErrorMsg(res.message ?? "Failed to download the sample.");
    setSampleDl(null);
  }

  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(dryRun ? "preview" : "assign");
    setErrorMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    if (dryRun) fd.append("dry_run", "true");
    try {
      const { data } = await clientApi.post(API.assets.assignImport, fd, { headers: { "Content-Type": undefined } });
      if (dryRun) {
        setPreview(data.data);
      } else {
        setResult(data.data); setPreview(null); setConfirming(false);
        if (data.data.summary.assigned) onAssigned();
      }
    } catch (err) {
      setConfirming(false);
      setErrorMsg(apiMessage(err, dryRun ? "Could not check the file." : "Assignment failed."));
    } finally {
      setBusy(null);
    }
  }

  function downloadReport(b64: string) {
    const url = URL.createObjectURL(new Blob([decodeReport(b64)], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "asset_assignment_errors.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const ready = preview?.counts.ready ?? 0;
  const report = result?.error_report_csv ?? preview?.error_report_csv ?? null;

  return (
    <Modal
      title={<><i className="ti ti-users-group" style={{ marginRight: 8 }} />Bulk Assign Assets</>}
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
              <button className="btn btn-ghost" onClick={reset}>Assign another file</button>
              <button className="btn btn-filled" onClick={onClose}>Done</button>
            </>
          ) : preview && confirming ? (
            <>
              <button className="btn btn-ghost" onClick={() => setConfirming(false)} disabled={!!busy}>Back</button>
              <button className="btn btn-filled" onClick={() => send(false)} disabled={!!busy}>
                {busy === "assign" ? "Assigning…" : `Yes, assign ${ready} asset(s)`}
              </button>
            </>
          ) : preview ? (
            <>
              <button className="btn btn-ghost" onClick={reset} disabled={!!busy}>Cancel</button>
              <button className="btn btn-filled" onClick={() => setConfirming(true)} disabled={!!busy || ready === 0}>
                {`Assign ${ready} asset(s)…`}
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
              Upload a CSV or Excel (.xlsx) file with one existing asset and one employee per row (up to 1000 rows, 5 MB).
              Only Available assets can be assigned; assets that are already assigned are reported, never reassigned.
              Nothing is assigned until you confirm.
            </div>
            <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
              <strong>Required columns:</strong> {ASSET_ASSIGN_COLUMNS.filter(c => c.required).map(c => c.header).join(", ")}.{" "}
              <strong>Optional:</strong> {ASSET_ASSIGN_COLUMNS.filter(c => !c.required).map(c => c.header).join(", ")}.
              Condition is new, good, fair or damaged; dates as YYYY-MM-DD.
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
                Preview (nothing assigned yet): <strong>{preview.counts.ready}</strong> ready,{" "}
                <strong>{preview.counts.already_assigned}</strong> already assigned,{" "}
                <strong>{preview.counts.error}</strong> with errors. Only ready rows are assigned.
              </div>
            </div>
            {confirming && (
              <div className="alert alert-warn">
                <i className="ti ti-alert-triangle" />
                <div>
                  Assign <strong>{ready}</strong> asset(s) to the employees listed as Ready? Each row is checked again
                  before saving; anything that changed since this preview is reported instead of assigned.
                </div>
              </div>
            )}
            <Rows rows={preview.rows} />
          </>
        )}

        {result && (
          <>
            <div className={`alert ${result.summary.failed ? "alert-warn" : "alert-success"}`}>
              <i className={`ti ${result.summary.failed ? "ti-alert-triangle" : "ti-circle-check"}`} />
              <div>
                Finished: <strong>{result.summary.assigned}</strong> assigned,{" "}
                <strong>{result.summary.already_assigned}</strong> already assigned,{" "}
                <strong>{result.summary.failed}</strong> failed, <strong>{result.summary.skipped}</strong> skipped
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
