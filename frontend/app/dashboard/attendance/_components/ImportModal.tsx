"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import Modal from "@/components/Modal";
import EmployeePickerField, { type PickedEmployee } from "@/app/dashboard/separation/_components/EmployeePickerField";
import type { ImportPreview, ImportResult, ImportRowAction, ImportRowError } from "@/types/attendance";

type Mode = "single" | "bulk";

interface Props {
  onClose:    () => void;
  onImported: (result: ImportResult) => void;
}

const ACTION_LABEL: Record<ImportRowAction, { text: string; color: string }> = {
  create:          { text: "New record",              color: "var(--success)" },
  create_on_leave: { text: "New (approved leave day)", color: "var(--info)" },
  update:          { text: "Replaces existing",       color: "var(--warn)" },
  skip_on_leave:   { text: "Skipped — on leave",      color: "var(--on-variant)" },
  skip_duplicate:  { text: "Skipped — duplicate row", color: "var(--on-variant)" },
};

const CELL: React.CSSProperties = { padding: "7px 10px", textAlign: "left", whiteSpace: "nowrap" };

function downloadBase64Csv(base64: string, filename: string) {
  const link = document.createElement("a");
  link.href = `data:text/csv;base64,${base64}`;
  link.download = filename;
  link.click();
}

function StatTiles({ tiles }: { tiles: { label: string; value: number; color: string }[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))", gap: 8, marginBottom: 16 }}>
      {tiles.map(t => (
        <div key={t.label} style={{ padding: "10px 8px", borderRadius: 8, textAlign: "center", border: "1px solid var(--outline-v)", background: "var(--bg-low)" }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: t.value > 0 ? t.color : "var(--on-variant)" }}>{t.value}</div>
          <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>{t.label}</div>
        </div>
      ))}
    </div>
  );
}

function ErrorTable({ errors, total, reportCsv }: { errors: ImportRowError[]; total: number; reportCsv?: string }) {
  if (errors.length === 0) return null;
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>
          <i className="ti ti-alert-circle" style={{ marginRight: 5, color: "var(--error)" }} />
          {total} row{total !== 1 ? "s" : ""} with errors (not imported)
        </div>
        {reportCsv && (
          <button className="btn btn-ghost btn-sm" onClick={() => downloadBase64Csv(reportCsv, "attendance_import_errors.csv")}>
            <i className="ti ti-download" /> Download Error Report
          </button>
        )}
      </div>
      <div style={{ border: "1px solid var(--outline-v)", borderRadius: 8, maxHeight: 220, overflow: "auto" }}>
        <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "var(--bg-low)", position: "sticky", top: 0 }}>
              <th style={CELL}>Row</th><th style={CELL}>Employee</th><th style={CELL}>Date</th>
              <th style={{ ...CELL, whiteSpace: "normal" }}>Reason</th><th style={{ ...CELL, whiteSpace: "normal" }}>Resolution</th>
            </tr>
          </thead>
          <tbody>
            {errors.map((e, i) => (
              <tr key={i} style={{ borderTop: "1px solid var(--outline-v)" }}>
                <td style={CELL}>{e.row || "—"}</td>
                <td style={CELL}>{e.employee_name || e.employee_id || "—"}</td>
                <td style={CELL}>{e.attendance_date || "—"}</td>
                <td style={{ ...CELL, whiteSpace: "normal", color: "var(--error)" }}>{e.reason}</td>
                <td style={{ ...CELL, whiteSpace: "normal", color: "var(--on-variant)" }}>{e.resolution}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ImportModal({ onClose, onImported }: Props) {
  const [mode,      setMode]      = useState<Mode>("single");
  const [employee,  setEmployee]  = useState<PickedEmployee | null>(null);
  const [dateFrom,  setDateFrom]  = useState("");
  const [dateTo,    setDateTo]    = useState("");
  const [file,      setFile]      = useState<File | null>(null);
  const [dragOver,  setDragOver]  = useState(false);
  const [busy,      setBusy]      = useState<"preview" | "import" | null>(null);
  const [error,     setError]     = useState<string | null>(null);
  const [preview,   setPreview]   = useState<ImportPreview | null>(null);
  const [result,    setResult]    = useState<ImportResult | null>(null);
  const [sampleBusy, setSampleBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function resetToForm() {
    setPreview(null);
    setResult(null);
    setError(null);
  }

  function changeMode(next: Mode) {
    if (busy) return;
    setMode(next);
    resetToForm();
  }

  async function downloadSample() {
    setSampleBusy(true);
    const res = await downloadBlobFile(API.attendance.importSample, { format: "csv" }, "attendance_import_sample.csv");
    if (!res.success) setError(res.message ?? "Failed to download sample file.");
    setSampleBusy(false);
  }

  function buildForm(dryRun: boolean): FormData | null {
    if (!file) { setError("Please select a CSV file."); return null; }
    if (mode === "single" && !employee) { setError("Please select an employee."); return null; }
    if (dateFrom && dateTo && dateFrom > dateTo) { setError("The From date must be on or before the To date."); return null; }
    const form = new FormData();
    form.append("file", file);
    if (mode === "single" && employee) form.append("employee_id", employee.code);
    if (mode === "single" && dateFrom) form.append("date_from", dateFrom);
    if (mode === "single" && dateTo) form.append("date_to", dateTo);
    if (dryRun) form.append("dry_run", "true");
    return form;
  }

  async function runPreview() {
    if (busy) return;
    const form = buildForm(true);
    if (!form) return;
    setBusy("preview");
    setError(null);
    try {
      const res = await clientApi.post<{ data: ImportPreview }>(API.attendance.import, form);
      setPreview(res.data?.data ?? null);
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Failed to check the file.");
    } finally {
      setBusy(null);
    }
  }

  async function confirmImport() {
    if (busy) return;
    const form = buildForm(false);
    if (!form) return;
    setBusy("import");
    setError(null);
    try {
      const res = await clientApi.post<{ data: ImportResult }>(API.attendance.import, form);
      setResult(res.data?.data ?? null);
      setPreview(null);
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Failed to import attendance file.");
    } finally {
      setBusy(null);
    }
  }

  const importable = preview ? preview.to_create + preview.to_update : 0;
  const step: "form" | "preview" | "result" = result ? "result" : preview ? "preview" : "form";

  const footer =
    step === "form" ? (
      <>
        <button className="btn btn-ghost" onClick={onClose} disabled={!!busy}>Cancel</button>
        <button className="btn btn-filled" onClick={runPreview} disabled={!!busy || !file || (mode === "single" && !employee)}>
          {busy === "preview" ? <><i className="ti ti-loader-2 spin" /> Checking…</> : <><i className="ti ti-eye" /> Preview</>}
        </button>
      </>
    ) : step === "preview" ? (
      <>
        <button className="btn btn-ghost" onClick={resetToForm} disabled={!!busy}>Back</button>
        <button className="btn btn-filled" onClick={confirmImport} disabled={!!busy || importable === 0}>
          {busy === "import"
            ? <><i className="ti ti-loader-2 spin" /> Importing…</>
            : <><i className="ti ti-upload" /> Import {importable} record{importable !== 1 ? "s" : ""}</>}
        </button>
      </>
    ) : (
      <>
        {result && result.failed > 0 && result.status !== "queued" && (
          <button className="btn btn-ghost" onClick={() => { resetToForm(); setFile(null); }}>Import Another File</button>
        )}
        <button className="btn btn-filled" onClick={() => result && onImported(result)}>Done</button>
      </>
    );

  return (
    <Modal
      title={<><i className="ti ti-upload" style={{ marginRight: 8, color: "var(--primary)" }} />Import Attendance</>}
      onClose={busy ? () => {} : onClose}
      maxWidth={760}
      footer={footer}
    >
      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> <span>{error}</span></div>}

      {step === "form" && (
        <>
          {/* Mode choice */}
          <div role="radiogroup" aria-label="Import mode" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10, marginBottom: 16 }}>
            {([
              { key: "single", icon: "ti-user",  title: "Import for One Employee",   sub: "Upload attendance for a single selected employee." },
              { key: "bulk",   icon: "ti-users", title: "Import for All Employees", sub: "One file with rows for many employees." },
            ] as const).map(opt => {
              const active = mode === opt.key;
              return (
                <button
                  key={opt.key} type="button" role="radio" aria-checked={active} onClick={() => changeMode(opt.key)}
                  style={{
                    textAlign: "left", padding: "12px 14px", borderRadius: 8, cursor: "pointer",
                    border: `1.5px solid ${active ? "var(--primary)" : "var(--outline-v)"}`,
                    background: active ? "rgba(30,78,140,0.05)" : "transparent",
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 13, color: active ? "var(--primary)" : "var(--on-bg)" }}>
                    <i className={`ti ${opt.icon}`} style={{ marginRight: 6 }} />{opt.title}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>{opt.sub}</div>
                </button>
              );
            })}
          </div>

          {mode === "single" && (
            <>
              <div className="field-group">
                <label className="field-label">Employee <span style={{ color: "var(--error)" }}>*</span></label>
                <EmployeePickerField value={employee} onChange={setEmployee} placeholder="Search by employee name or ID…" />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
                <div className="field-group">
                  <label className="field-label">From date (optional)</label>
                  <input type="date" className="field-input" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
                </div>
                <div className="field-group">
                  <label className="field-label">To date (optional)</label>
                  <input type="date" className="field-input" value={dateTo} onChange={e => setDateTo(e.target.value)} />
                </div>
              </div>
            </>
          )}

          <div className="alert alert-info mb-16">
            <i className="ti ti-info-circle" />
            <span>
              <strong>CSV columns:</strong> employee_id, date, punch_in, punch_out — CSV only, max 5 MB.
              {mode === "single"
                ? " Every row must belong to the selected employee; employee_id may be left blank."
                : " Each row's employee_id decides whose attendance it is."}
              <code style={{ display: "block", marginTop: 6, fontSize: 11 }}>EMP001,2026-07-02,09:05,18:15</code>
            </span>
          </div>

          <button className="btn btn-ghost btn-sm mb-16" onClick={downloadSample} disabled={sampleBusy}>
            <i className="ti ti-download" /> {sampleBusy ? "Downloading…" : "Download sample CSV"}
          </button>

          <div
            className="upload-zone"
            role="button" tabIndex={0}
            style={{ cursor: "pointer", borderColor: dragOver ? "var(--primary)" : undefined }}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInputRef.current?.click(); } }}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files?.[0]; if (f) { setFile(f); setError(null); } }}
          >
            <i className="ti ti-folder-open" />
            <p style={{ fontWeight: 500, marginBottom: 4 }}>{file ? file.name : "Click to select file or drag & drop"}</p>
            <small>CSV — max 5 MB</small>
          </div>
          <input
            ref={fileInputRef} type="file" accept=".csv" style={{ display: "none" }}
            onChange={e => { setFile(e.target.files?.[0] ?? null); setError(null); }}
          />
        </>
      )}

      {step === "preview" && preview && (
        <>
          <div className="alert alert-info mb-16">
            <i className="ti ti-eye" />
            <span>
              {preview.employee ? <><strong>{preview.employee.full_name}</strong> ({preview.employee.employee_id}) — </> : <><strong>All employees</strong> — </>}
              {preview.message}
            </span>
          </div>
          <StatTiles tiles={[
            { label: "Rows in file",       value: preview.total_records, color: "var(--primary)" },
            { label: "New records",        value: preview.to_create,     color: "var(--success)" },
            { label: "Replace existing",   value: preview.to_update,     color: "var(--warn)" },
            { label: "Skipped",            value: preview.skipped,       color: "var(--warn)" },
            { label: "Errors",             value: preview.failed,        color: "var(--error)" },
          ]} />
          {preview.to_update > 0 && (
            <div className="alert alert-warn mb-16">
              <i className="ti ti-alert-triangle" />
              <span>{preview.to_update} row(s) will replace the punch times of an existing attendance record for that day.</span>
            </div>
          )}
          <ErrorTable errors={preview.errors} total={preview.failed} reportCsv={preview.error_report_csv} />
          {preview.rows.length > 0 && (
            <>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                Rows to import{preview.rows_truncated ? ` (first ${preview.rows.length} shown)` : ""}
              </div>
              <div style={{ border: "1px solid var(--outline-v)", borderRadius: 8, maxHeight: 260, overflow: "auto" }}>
                <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ background: "var(--bg-low)", position: "sticky", top: 0 }}>
                      <th style={CELL}>Row</th><th style={CELL}>Employee</th><th style={CELL}>Date</th>
                      <th style={CELL}>In</th><th style={CELL}>Out</th><th style={CELL}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map(r => (
                      <tr key={`${r.row}-${r.action}`} style={{ borderTop: "1px solid var(--outline-v)" }}>
                        <td style={CELL}>{r.row}</td>
                        <td style={CELL}>{r.employee_name} <span style={{ color: "var(--on-variant)" }}>· {r.employee_id}</span></td>
                        <td style={CELL}>{r.date}</td>
                        <td style={CELL}>{r.punch_in || "—"}</td>
                        <td style={CELL}>{r.punch_out || "—"}</td>
                        <td style={{ ...CELL, color: ACTION_LABEL[r.action].color, fontWeight: 600 }}>{ACTION_LABEL[r.action].text}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}

      {step === "result" && result && (
        result.status === "queued" ? (
          <div className="alert alert-info"><i className="ti ti-clock" /> <span>{result.message.split(" Poll ")[0]} You can close this window; refresh the attendance list in a few minutes.</span></div>
        ) : (
          <>
            <div className={`alert ${result.failed > 0 ? (result.successful > 0 ? "alert-warn" : "alert-error") : "alert-success"} mb-16`}>
              <i className={`ti ${result.failed > 0 ? "ti-alert-triangle" : "ti-circle-check"}`} />
              <span>{result.message}</span>
            </div>
            <StatTiles tiles={[
              { label: "Total",      value: result.total_records, color: "var(--primary)" },
              { label: "Successful", value: result.successful,    color: "var(--success)" },
              { label: "Failed",     value: result.failed,        color: "var(--error)" },
              { label: "Skipped",    value: result.skipped,       color: "var(--warn)" },
            ]} />
            <ErrorTable errors={result.errors} total={result.failed} reportCsv={result.error_report_csv} />
          </>
        )
      )}
    </Modal>
  );
}
