"use client";

// Settings → Leave Management → Monthly Leave Management.
// Import and manual entry both call the same backend rule
// (set_monthly_credit): a month's credit is set to a value, only the
// difference is applied to the employee's leave balance, and history is kept.

import { useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import CollapsibleCard from "./CollapsibleCard";
import MonthlyAssignmentsSection from "./MonthlyAssignmentsSection";
import {
  MONTHS, STATUS_LABEL, annualWarningTypes, creditYears, selectAllState, toggleAllShown, unselectableReason,
  validateMonthlyCredit,
  type ImportRowStatus, type MonthlyImportPreview, type MonthlyImportResult, type MonthlyImportRow,
  type PickableEmployee,
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
  );
}

// ─── B. Manual entry (one or many employees) ─────────────────────────────────

interface LeaveTypeOption { leave_type: string; label: string; annual_days: number }

const PAGE_SIZE = 50;

function ManualEntrySection({ active, onChanged }: { active: boolean; onChanged: () => void }) {
  const now = new Date();
  const user = useCurrentUser();
  const me = user?.userId ?? null;

  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<PickableEmployee[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Map<string, PickableEmployee>>(new Map());
  const [leaveTypes, setLeaveTypes] = useState<LeaveTypeOption[] | null>(null);
  const [leaveType, setLeaveType] = useState("");
  const [credit, setCredit] = useState("");
  const [review, setReview] = useState<MonthlyImportPreview | null>(null);
  const [result, setResult] = useState<MonthlyImportResult | null>(null);
  const [busy, setBusy] = useState<"review" | "save" | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);

  // Debounce typing into the search used for the request.
  useEffect(() => {
    // A new search always starts from page 1 (both updates batch into one render).
    const t = setTimeout(() => { setSearch(query.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [query]);

  // Employees from the existing, server-scoped directory (Branch Admin → own
  // branch, System Admin → all branches, managers → their team). Loaded only
  // once the section has been opened.
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    setListLoading(true);
    setListError(null);
    clientApi
      .get(API.employees.list, { params: { search, page, page_size: PAGE_SIZE } })
      .then(({ data }) => {
        if (cancelled) return;
        const found: PickableEmployee[] = (data.data?.results ?? []).map((r: PickableEmployee) => ({
          uuid: r.uuid, employee_id: r.employee_id, full_name: r.full_name,
          branch: r.branch ?? "", department: r.department ?? "", is_active: r.is_active !== false,
        }));
        setRows(prev => (page === 1 ? found : [...prev, ...found]));
        setTotalPages(data.data?.total_pages ?? 1);
      })
      .catch(err => { if (!cancelled) { setRows([]); setListError(apiMessage(err, "Could not load employees.")); } })
      .finally(() => { if (!cancelled) setListLoading(false); });
    return () => { cancelled = true; };
  }, [active, search, page]);

  useEffect(() => {
    if (!active || leaveTypes) return;
    clientApi
      .get(API.leave.policy)
      .then(({ data }) => setLeaveTypes(
        (data.data ?? [])
          .filter((p: { is_active: boolean; leave_type: string }) => p.is_active && p.leave_type !== "lwp")
          .map((p: { leave_type: string; leave_type_display?: string; annual_days: number | string }) => ({
            leave_type: p.leave_type, label: p.leave_type_display || p.leave_type, annual_days: Number(p.annual_days) || 0,
          })),
      ))
      .catch(err => setErrorMsg(apiMessage(err, "Could not load leave types.")));
  }, [active, leaveTypes]);

  // Any change to what would be saved makes an earlier review stale.
  useEffect(() => { setReview(null); }, [selected, leaveType, credit, month, year]);

  const all = selectAllState(rows, new Set(selected.keys()), me);
  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = all.indeterminate;
  }, [all.indeterminate]);

  const creditError = credit ? validateMonthlyCredit(credit) : null;
  const typeInfo = leaveTypes?.find(t => t.leave_type === leaveType) ?? null;
  const canReview = selected.size > 0 && !!leaveType && credit.trim() !== "" && !creditError && !busy;

  function toggle(emp: PickableEmployee, check: boolean) {
    setResult(null);
    setSelected(prev => {
      const next = new Map(prev);
      if (check) next.set(emp.employee_id, emp); else next.delete(emp.employee_id);
      return next;
    });
  }

  async function send(dryRun: boolean) {
    setBusy(dryRun ? "review" : "save");
    setErrorMsg(null);
    try {
      const { data } = await clientApi.post(API.leave.monthlyCreditsBulk, {
        employee_ids: [...selected.keys()], leave_type: leaveType, year, month, credit: credit.trim(),
        ...(dryRun ? { dry_run: true } : {}),
      });
      if (dryRun) { setReview(data.data); setResult(null); }
      else { setResult(data.data); setReview(null); onChanged(); }
    } catch (err) {
      setErrorMsg(apiMessage(err, dryRun ? "Could not prepare the review." : "Could not save. Employees that failed were not changed."));
    } finally {
      setBusy(null);
    }
  }

  const applicable = review ? review.counts.new + review.counts.update : 0;

  return (
    <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ fontSize: 12.5, color: "var(--on-variant)", lineHeight: 1.5 }}>
        Tick one or more employees, choose the month, leave type and credit, then review and confirm. Each
        employee&apos;s credit is set to this value; only the difference is applied to their balance, and 0 removes it.
      </div>

      <MonthYearFields month={month} year={year} onMonth={setMonth} onYear={setYear} disabled={!!busy} />

      {/* Employee checklist */}
      <div className="field-group">
        <label className="field-label">Employees</label>
        <input className="field-input" placeholder="Search by name or employee code…" value={query}
          onChange={e => setQuery(e.target.value)} />
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", margin: "10px 0 6px", fontSize: 13 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: all.selectable ? "pointer" : "default" }}>
            <input ref={selectAllRef} type="checkbox" checked={all.checked} disabled={!all.selectable || !!busy}
              onChange={e => { setResult(null); setSelected(prev => toggleAllShown(rows, prev, e.target.checked, me)); }} />
            Select all shown ({all.selectable})
          </label>
          <span style={{ color: "var(--on-variant)" }}><strong>{selected.size}</strong> selected</span>
          {selected.size > 0 && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setSelected(new Map()); setResult(null); }} disabled={!!busy}>
              <i className="ti ti-x" /> Clear selection
            </button>
          )}
        </div>
        <div style={{ border: "1px solid var(--outline-v)", borderRadius: 8, maxHeight: 300, overflowY: "auto" }}>
          {listError ? (
            <div style={{ padding: 12, fontSize: 13, color: "var(--error)" }}>{listError}</div>
          ) : rows.length === 0 && listLoading ? (
            <div style={{ padding: 12, fontSize: 13, color: "var(--on-variant)" }}><Spin /> Loading employees…</div>
          ) : rows.length === 0 ? (
            <div style={{ padding: 12, fontSize: 13, color: "var(--on-variant)" }}>No employees found.</div>
          ) : (
            <>
              {rows.map(emp => {
                const reason = unselectableReason(emp, me);
                return (
                  <label key={emp.employee_id} style={{
                    display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", fontSize: 13,
                    borderBottom: "1px solid var(--outline-v)", cursor: reason ? "default" : "pointer",
                    opacity: reason ? 0.6 : 1,
                  }}>
                    <input type="checkbox" disabled={!!reason || !!busy} checked={selected.has(emp.employee_id)}
                      onChange={e => toggle(emp, e.target.checked)} />
                    <span style={{ minWidth: 0 }}>
                      <strong>{emp.full_name}</strong>
                      <span style={{ color: "var(--on-variant)" }}>
                        {" "}· {emp.employee_id}{emp.branch ? ` · ${emp.branch}` : ""}{emp.department ? ` · ${emp.department}` : ""}
                        {reason === "you" && " · you (cannot change your own credits)"}
                        {reason === "inactive" && " · inactive"}
                      </span>
                    </span>
                  </label>
                );
              })}
              {page < totalPages && (
                <div style={{ padding: 8, textAlign: "center" }}>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPage(p => p + 1)} disabled={listLoading}>
                    {listLoading ? <><Spin /> Loading…</> : "Load more"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
        {page < totalPages && (
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
            Select all applies to the employees shown. Load more or search to include others.
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <div className="field-group" style={{ minWidth: 220 }}>
          <label className="field-label">Leave type</label>
          <select className="field-input" value={leaveType} disabled={!!busy || !leaveTypes}
            onChange={e => { setLeaveType(e.target.value); setResult(null); }}>
            <option value="">{leaveTypes ? "Select a leave type…" : "Loading…"}</option>
            {leaveTypes?.map(t => <option key={t.leave_type} value={t.leave_type}>{t.label}</option>)}
          </select>
        </div>
        <div className="field-group" style={{ maxWidth: 220 }}>
          <label className="field-label">Monthly leave credit (days)</label>
          <input className={`field-input${creditError ? " field-error" : ""}`} inputMode="decimal" value={credit}
            disabled={!!busy} onChange={e => { setCredit(e.target.value); setResult(null); }} />
          {creditError
            ? <div className="field-error-msg">{creditError}</div>
            : <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>0–31, one decimal place. 0 removes the month&apos;s credit.</div>}
        </div>
      </div>

      {typeInfo && typeInfo.annual_days > 0 && (
        <AnnualWarning types={[`${typeInfo.label} (${typeInfo.annual_days} days/year)`]} />
      )}
      {errorMsg && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{errorMsg}</div></div>}

      {!review && (
        <div>
          <button className="btn btn-filled" onClick={() => send(true)} disabled={!canReview}>
            {busy === "review" ? <><Spin /> Checking…</> : <><i className="ti ti-eye" /> Review ({selected.size})</>}
          </button>
        </div>
      )}

      {review && (
        <>
          <div className={`alert ${review.counts.error ? "alert-warn" : "alert-info"}`}>
            <i className="ti ti-list-check" />
            <div>
              Review (nothing saved yet): set <strong>{typeInfo?.label ?? leaveType}</strong> to{" "}
              <strong>{credit.trim()} day(s)</strong> for <strong>{MONTHS[review.month - 1]} {review.year}</strong> —{" "}
              <strong>{review.counts.new}</strong> new, <strong>{review.counts.update}</strong> update,{" "}
              <strong>{review.counts.unchanged}</strong> unchanged, <strong>{review.counts.error}</strong> cannot be changed.
            </div>
          </div>
          <RowsTable rows={review.rows} />
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button className="btn btn-ghost" onClick={() => setReview(null)} disabled={!!busy}>Back</button>
            <button className="btn btn-filled" onClick={() => send(false)} disabled={!!busy || applicable === 0}>
              {busy === "save" ? <><Spin /> Saving…</> : <><i className="ti ti-check" /> Confirm for {applicable} employee(s)</>}
            </button>
          </div>
        </>
      )}

      {result && (
        <>
          <div className={`alert ${result.summary.failed ? "alert-warn" : "alert-success"}`}>
            <i className={`ti ${result.summary.failed ? "ti-alert-triangle" : "ti-circle-check"}`} />
            <div>
              {MONTHS[result.month - 1]} {result.year}: <strong>{result.summary.created}</strong> added,{" "}
              <strong>{result.summary.updated}</strong> updated, <strong>{result.summary.skipped}</strong> unchanged or skipped,{" "}
              <strong>{result.summary.failed}</strong> failed. Employees that failed were not changed.
            </div>
          </div>
          <RowsTable rows={result.rows} />
        </>
      )}
    </div>
  );
}

export default function MonthlyLeaveTab() {
  // Bumped after every successful import, manual save or edit so the
  // assignments list and its summary reload from the server.
  const [refreshKey, setRefreshKey] = useState(0);
  const changed = () => setRefreshKey(k => k + 1);
  // All sections start collapsed; each keeps its own state while collapsed.
  const [importOpen, setImportOpen] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualOpened, setManualOpened] = useState(false);
  return (
    <>
      <CollapsibleCard icon="ti-file-upload" title="Monthly Leave Import" open={importOpen} onToggle={() => setImportOpen(o => !o)}>
        <MonthlyImportSection onChanged={changed} />
      </CollapsibleCard>
      <CollapsibleCard icon="ti-edit" title="Manual Monthly Leave Entry" open={manualOpen}
        onToggle={() => { setManualOpen(o => !o); setManualOpened(true); }}>
        <ManualEntrySection active={manualOpened} onChanged={changed} />
      </CollapsibleCard>
      <MonthlyAssignmentsSection refreshKey={refreshKey} onChanged={changed} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}
