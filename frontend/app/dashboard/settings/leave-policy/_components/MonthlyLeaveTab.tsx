"use client";

// Settings → Leave Management → Monthly Leave Management.
// Import and manual entry both call the same backend rule
// (set_monthly_credit): a month's credit is set to a value, only the
// difference is applied to the employee's leave balance, and history is kept.

import { useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import EmployeePickerField, { type PickedEmployee } from "@/app/dashboard/separation/_components/EmployeePickerField";
import MonthlyAssignmentsSection from "./MonthlyAssignmentsSection";
import {
  MONTHS, STATUS_LABEL, annualWarningTypes, creditYears, projectedBalance, validateMonthlyCredit,
  type ImportRowStatus, type MonthlyImportPreview, type MonthlyImportResult, type MonthlyImportRow,
  type MonthlyLeaveTypeRow,
} from "@/lib/monthlyLeave";

const MAX_FILE_BYTES = 5 * 1024 * 1024;

function apiMessage(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

function MonthYearFields({ month, year, onMonth, onYear, disabled }: {
  month: number; year: number; onMonth: (m: number) => void; onYear: (y: number) => void; disabled?: boolean;
}) {
  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      <div className="field-group" style={{ minWidth: 160 }}>
        <label className="field-label">Month</label>
        <select className="field-input" value={month} disabled={disabled} onChange={e => onMonth(Number(e.target.value))}>
          {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
        </select>
      </div>
      <div className="field-group" style={{ minWidth: 120 }}>
        <label className="field-label">Year</label>
        <select className="field-input" value={year} disabled={disabled} onChange={e => onYear(Number(e.target.value))}>
          {creditYears().map(y => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>
    </div>
  );
}

const STATUS_COLOR: Record<ImportRowStatus, string> = {
  new: "var(--success, #1a7f37)", update: "var(--primary)", unchanged: "var(--on-variant)",
  duplicate: "#9a6700", error: "var(--error)",
};

function RowsTable({ rows }: { rows: MonthlyImportRow[] }) {
  return (
    <div style={{ overflowX: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
      <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
        <thead>
          <tr>
            <th>Row</th><th>Employee</th><th>Leave Type</th>
            <th style={{ textAlign: "right" }}>Credit</th><th style={{ textAlign: "right" }}>Current</th>
            <th style={{ textAlign: "right" }}>Change</th><th>Status</th><th>Details</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.row}>
              <td>{r.row}</td>
              <td>{r.employee_code}{r.employee_name ? <div style={{ color: "var(--on-variant)" }}>{r.employee_name}</div> : null}</td>
              <td>{r.leave_type_label ?? r.leave_type}</td>
              <td style={{ textAlign: "right" }}>{r.credit}</td>
              <td style={{ textAlign: "right" }}>{r.previous ?? "—"}</td>
              <td style={{ textAlign: "right" }}>{r.delta == null ? "—" : `${r.delta > 0 ? "+" : ""}${r.delta}`}</td>
              <td style={{ color: STATUS_COLOR[r.status], fontWeight: 600 }}>{STATUS_LABEL[r.status]}</td>
              <td style={{ color: "var(--on-variant)" }}>{r.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AnnualWarning({ types }: { types: string[] }) {
  if (!types.length) return null;
  return (
    <div className="alert alert-warn mb-16">
      <i className="ti ti-alert-triangle" />
      <div>
        <strong>Possible double-counting:</strong> {types.join(", ")} also {types.length > 1 ? "have" : "has"} an
        annual entitlement. Monthly credits are added on top of whatever is already in the balance. Use them only if
        that leave type isn&apos;t also credited annually.
      </div>
    </div>
  );
}

// ─── A. Import ────────────────────────────────────────────────────────────────

function MonthlyImportSection({ onChanged }: { onChanged: () => void }) {
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<MonthlyImportPreview | null>(null);
  const [result, setResult] = useState<MonthlyImportResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "import" | null>(null);
  const [sampleDl, setSampleDl] = useState<"csv" | "xlsx" | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function reset() {
    setFile(null); setPreview(null); setResult(null); setErrorMsg(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function pickFile(f: File | undefined) {
    setPreview(null); setResult(null); setErrorMsg(null);
    if (!f) return;
    const name = f.name.toLowerCase();
    if (!name.endsWith(".csv") && !name.endsWith(".xlsx")) { setErrorMsg("Upload a .csv or .xlsx file."); return; }
    if (f.size > MAX_FILE_BYTES) { setErrorMsg("File must not exceed 5 MB."); return; }
    setFile(f);
  }

  async function sample(format: "csv" | "xlsx") {
    setSampleDl(format);
    const res = await downloadBlobFile(API.leave.monthlyCreditsSample, { format }, `monthly_leave_credit_sample.${format}`);
    if (!res.success) setErrorMsg(res.message ?? "Failed to download the sample.");
    setSampleDl(null);
  }

  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(dryRun ? "preview" : "import");
    setErrorMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("year", String(year));
    fd.append("month", String(month));
    if (dryRun) fd.append("dry_run", "true");
    try {
      const { data } = await clientApi.post(API.leave.monthlyCreditsImport, fd, { headers: { "Content-Type": undefined } });
      if (dryRun) { setPreview(data.data); setResult(null); }
      else { setResult(data.data); setPreview(null); onChanged(); }
    } catch (err) {
      setErrorMsg(apiMessage(err, dryRun ? "Could not preview the file." : "Import failed. Nothing was changed for rows that failed."));
    } finally {
      setBusy(null);
    }
  }

  const applicable = preview ? preview.counts.new + preview.counts.update : 0;
  const warn = preview ? annualWarningTypes(preview.rows, preview.annual_entitlements) : [];

  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-file-upload" /> Monthly Leave Import</div>
      </div>
      <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ fontSize: 12.5, color: "var(--on-variant)", lineHeight: 1.5 }}>
          Set each employee&apos;s leave credit for one month. Columns: <strong>Employee Code</strong>,{" "}
          <strong>Leave Type</strong>, <strong>Monthly Leave Credit</strong>. Re-importing the same file changes
          nothing; a different value replaces the month&apos;s credit, and 0 removes it.
        </div>

        <MonthYearFields month={month} year={year} disabled={!!busy || !!preview}
          onMonth={m => { setMonth(m); setPreview(null); setResult(null); }}
          onYear={y => { setYear(y); setPreview(null); setResult(null); }} />

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button className="btn btn-ghost btn-sm" onClick={() => sample("csv")} disabled={!!sampleDl}>
            <i className="ti ti-download" /> {sampleDl === "csv" ? "Downloading…" : "Sample CSV"}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => sample("xlsx")} disabled={!!sampleDl}>
            <i className="ti ti-download" /> {sampleDl === "xlsx" ? "Downloading…" : "Sample Excel"}
          </button>
          <label className="btn btn-ghost btn-sm" style={{ cursor: busy ? "default" : "pointer" }}>
            <i className="ti ti-upload" /> {file ? "Choose another file" : "Choose CSV / Excel file"}
            <input ref={inputRef} type="file" accept=".csv,.xlsx" hidden disabled={!!busy}
              onChange={e => pickFile(e.target.files?.[0])} />
          </label>
          {file && <span style={{ fontSize: 12.5 }}><i className="ti ti-file" /> {file.name}</span>}
        </div>

        {errorMsg && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{errorMsg}</div></div>}

        {!preview && !result && (
          <div>
            <button className="btn btn-filled" onClick={() => send(true)} disabled={!file || !!busy}>
              {busy === "preview" ? <><Spin /> Checking…</> : <><i className="ti ti-eye" /> Preview</>}
            </button>
          </div>
        )}

        {preview && (
          <>
            <div className={`alert ${preview.counts.error ? "alert-warn" : "alert-info"}`}>
              <i className="ti ti-list-check" />
              <div>
                Preview for {MONTHS[preview.month - 1]} {preview.year} (nothing saved yet):{" "}
                <strong>{preview.counts.new}</strong> new, <strong>{preview.counts.update}</strong> update,{" "}
                <strong>{preview.counts.unchanged}</strong> unchanged, <strong>{preview.counts.duplicate}</strong> duplicate,{" "}
                <strong>{preview.counts.error}</strong> error. Only new and update rows will be applied.
              </div>
            </div>
            <AnnualWarning types={warn} />
            <RowsTable rows={preview.rows} />
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={reset} disabled={!!busy}>Cancel</button>
              <button className="btn btn-filled" onClick={() => send(false)} disabled={!!busy || applicable === 0}>
                {busy === "import" ? <><Spin /> Importing…</> : <><i className="ti ti-check" /> Confirm import ({applicable})</>}
              </button>
            </div>
          </>
        )}

        {result && (
          <>
            <div className={`alert ${result.summary.failed ? "alert-warn" : "alert-success"}`}>
              <i className={`ti ${result.summary.failed ? "ti-alert-triangle" : "ti-circle-check"}`} />
              <div>
                Import for {MONTHS[result.month - 1]} {result.year} finished:{" "}
                <strong>{result.summary.created}</strong> added, <strong>{result.summary.updated}</strong> updated,{" "}
                <strong>{result.summary.skipped}</strong> skipped, <strong>{result.summary.failed}</strong> failed
                (of {result.summary.total} rows). Failed rows changed nothing.
              </div>
            </div>
            <RowsTable rows={result.rows} />
            <div><button className="btn btn-ghost" onClick={reset}>Import another file</button></div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── B. Manual entry ──────────────────────────────────────────────────────────

function ManualEntrySection({ onChanged }: { onChanged: () => void }) {
  const now = new Date();
  const [employee, setEmployee] = useState<PickedEmployee | null>(null);
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [rows, setRows] = useState<MonthlyLeaveTypeRow[] | null>(null);
  const [leaveType, setLeaveType] = useState("");
  const [credit, setCredit] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  useEffect(() => {
    setRows(null); setOkMsg(null); setErrorMsg(null);
    if (!employee) return;
    let cancelled = false;
    setLoading(true);
    clientApi
      .get(API.leave.monthlyCredits, { params: { employee_id: employee.code, year, month } })
      .then(({ data }) => { if (!cancelled) setRows(data.data.leave_types); })
      .catch(err => { if (!cancelled) setErrorMsg(apiMessage(err, "Could not load this employee's leave credits.")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [employee, year, month]);

  const selected = rows?.find(r => r.leave_type === leaveType) ?? null;
  useEffect(() => { setCredit(selected ? String(selected.monthly_credit) : ""); }, [selected?.leave_type, selected?.monthly_credit]); // eslint-disable-line react-hooks/exhaustive-deps

  const creditError = selected ? validateMonthlyCredit(credit) : null;
  const next = creditError ? null : Number(credit);
  const projection = selected && next !== null ? projectedBalance(selected, next) : null;
  const exists = !!selected && selected.monthly_credit > 0;
  const unchanged = !!selected && next === selected.monthly_credit;

  async function save() {
    if (!employee || !selected || creditError) return;
    setSaving(true); setErrorMsg(null); setOkMsg(null);
    try {
      const { data } = await clientApi.post(API.leave.monthlyCredits, {
        employee_id: employee.code, year, month, leave_type: selected.leave_type, credit: credit.trim(),
      });
      setRows(data.data.leave_types);
      setOkMsg(data.message);
      onChanged();
    } catch (err) {
      setErrorMsg(apiMessage(err, "Could not save the monthly credit."));
    } finally {
      setSaving(false);
    }
  }

  return (
    // overflow: visible so the employee search dropdown isn't clipped by .card's overflow: hidden
    <div className="card mb-24" style={{ overflow: "visible" }}>
      <div className="card-header">
        <div className="card-title"><i className="ti ti-edit" /> Manual Monthly Leave Entry</div>
      </div>
      <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="field-group">
          <label className="field-label">Employee</label>
          <EmployeePickerField value={employee} onChange={e => { setEmployee(e); setLeaveType(""); }}
            placeholder="Search an employee by name or code…" />
        </div>

        <MonthYearFields month={month} year={year} onMonth={setMonth} onYear={setYear} disabled={saving} />

        {loading && <div style={{ fontSize: 13, color: "var(--on-variant)" }}><Spin /> Loading…</div>}
        {errorMsg && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{errorMsg}</div></div>}
        {okMsg && <div className="alert alert-success"><i className="ti ti-circle-check" /><div>{okMsg}</div></div>}

        {rows && (
          <div className="field-group" style={{ maxWidth: 320 }}>
            <label className="field-label">Leave type</label>
            <select className="field-input" value={leaveType} onChange={e => { setLeaveType(e.target.value); setOkMsg(null); }}>
              <option value="">Select a leave type…</option>
              {rows.map(r => <option key={r.leave_type} value={r.leave_type}>{r.leave_type_label}</option>)}
            </select>
          </div>
        )}

        {selected && (
          <>
            {selected.annual_days > 0 && (
              <AnnualWarning types={[`${selected.leave_type_label} (${selected.annual_days} days/year)`]} />
            )}
            <div style={{ fontSize: 13 }}>
              Current credit for {MONTHS[month - 1]} {year}:{" "}
              <strong>{exists ? `${selected.monthly_credit} day(s)` : "none"}</strong>
            </div>
            <div className="field-group" style={{ maxWidth: 220 }}>
              <label className="field-label">Monthly leave credit (days)</label>
              <input className={`field-input${creditError ? " field-error" : ""}`} inputMode="decimal"
                value={credit} onChange={e => { setCredit(e.target.value); setOkMsg(null); }} />
              {creditError
                ? <div className="field-error-msg">{creditError}</div>
                : <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>0–31, one decimal place. 0 removes this month&apos;s credit.</div>}
            </div>

            <div style={{ fontSize: 12.5, color: "var(--on-variant)", lineHeight: 1.7 }}>
              {selected.balance
                ? <>Balance now: total <strong>{selected.balance.total}</strong>, used <strong>{selected.balance.used}</strong>,
                    pending <strong>{selected.balance.pending}</strong>, available <strong>{selected.balance.available}</strong>.</>
                : <>No {year} balance exists yet for this leave type{year === now.getFullYear() ? "; saving creates one" : ""}.</>}
              {projection && !unchanged && (
                <> After saving: total <strong>{projection.total}</strong>, available <strong>{projection.available}</strong>{" "}
                  ({projection.delta > 0 ? "+" : ""}{projection.delta}).</>
              )}
            </div>

            <div>
              <button className="btn btn-filled" onClick={save} disabled={saving || !!creditError || unchanged}>
                {saving ? <><Spin /> Saving…</> : <><i className="ti ti-device-floppy" /> {exists ? "Update" : "Save"}</>}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function MonthlyLeaveTab() {
  // Bumped after every successful import, manual save or edit so the
  // assignments list and its summary reload from the server.
  const [refreshKey, setRefreshKey] = useState(0);
  const changed = () => setRefreshKey(k => k + 1);
  return (
    <>
      <MonthlyImportSection onChanged={changed} />
      <ManualEntrySection onChanged={changed} />
      <MonthlyAssignmentsSection refreshKey={refreshKey} onChanged={changed} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}
