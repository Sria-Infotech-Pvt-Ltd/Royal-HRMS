"use client";

import { useState, useRef } from "react";
import Modal from "@/components/Modal";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";

interface Adjustment {
  id: string;
  employee: string;
  employee_name: string;
  employee_code: string;
  month: string;
  type: "addition" | "deduction" | "arrear";
  label: string;
  amount: string;
  created_by_name: string;
  created_at: string;
}

interface AdjustmentListResponse {
  results:          Adjustment[];
  count:            number;
  page:             number;
  page_size:        number;
  total_pages:      number;
  total_additions:  number | string;
  total_deductions: number | string;
}

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const TYPE_LABELS: Record<string, string> = { addition: "Addition", deduction: "Deduction", arrear: "Arrear" };
const TYPE_BADGE: Record<string, string> = { addition: "badge-success", deduction: "badge-error", arrear: "badge-warning" };
const PAGE_SIZE = 10;

function monthParam(month: string, year: string) {
  const idx = MONTHS.indexOf(month) + 1;
  return `${year}-${String(idx).padStart(2, "0")}`;
}

// Compact page-number list with "…" for long ranges — e.g. [1, "…", 4, 5, 6, "…", 12]
function getPageNumbers(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | "…")[] = [1];
  if (current > 3) pages.push("…");
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p++) pages.push(p);
  if (current < total - 2) pages.push("…");
  pages.push(total);
  return pages;
}

export default function PayrollAdjustments() {
  const canEdit = usePermission("payroll.edit");
  const today   = new Date();

  const [month,     setMonth]     = useState(MONTHS[today.getMonth()]);
  const [year,      setYear]      = useState(String(today.getFullYear()));
  const [page,      setPage]      = useState(1);
  const [showAdd,   setShowAdd]   = useState(false);
  const [saving,    setSaving]    = useState(false);
  const [saveMsg,   setSaveMsg]   = useState("");
  const [errMsg,    setErrMsg]    = useState("");
  const [addErr,    setAddErr]    = useState("");
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const param = monthParam(month, year);
  const { data, loading, refetch } = useFetch<AdjustmentListResponse>(
    `${API.payroll.adjustments}?month=${param}&page=${page}&page_size=${PAGE_SIZE}`,
  );
  const rows = data?.results ?? [];

  // Changing month/year should always land back on page 1 — otherwise a
  // page number valid for one month's row count can be out of range for
  // another and silently render nothing.
  function changeMonth(m: string) { setMonth(m); setPage(1); }
  function changeYear(y: string)  { setYear(y);  setPage(1); }

  // Add / Bulk Import both need to land back on page 1 and show fresh data.
  // If we're already on page 1, changing `page` to 1 is a no-op (same
  // state, no URL change, no automatic refetch) — refetch explicitly in
  // that case; otherwise setPage(1) itself changes the fetch URL and
  // triggers the refetch, so we don't double-fetch.
  function reloadFromPageOne() {
    if (page === 1) refetch();
    else setPage(1);
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this adjustment?")) return;
    setErrMsg("");
    try {
      await clientApi.delete(API.payroll.adjustmentDetail(id));
      // If that was the last row on a page beyond the first, step back a
      // page instead of landing on a now-empty page.
      if (rows.length === 1 && page > 1) {
        setPage(p => p - 1);
      } else {
        refetch();
      }
      setSaveMsg("Adjustment deleted.");
    } catch {
      setErrMsg("Failed to delete adjustment.");
    }
  }

  async function handleBulkImport(file: File) {
    setImporting(true);
    setErrMsg("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await clientApi.post(
        `${API.payroll.adjustmentsBulkImport}?month=${param}`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      const imported = res.data?.data?.imported ?? 0;
      const rowErrors = res.data?.data?.row_errors ?? [];
      reloadFromPageOne();
      if (rowErrors.length > 0) {
        setErrMsg(`${imported} imported. ${rowErrors.length} row(s) had errors:\n` +
          rowErrors.slice(0, 5).map((e: { row: number; error: string }) => `Row ${e.row}: ${e.error}`).join("\n"));
      } else {
        setSaveMsg(`${imported} adjustment(s) imported.`);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Import failed.";
      setErrMsg(msg);
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function downloadTemplate() {
    const csv = "employee_code,type,label,amount\nEMP001,addition,Festival Bonus,5000\nEMP002,deduction,Loan Recovery,2000\nEMP003,arrear,March Arrear,3500\n";
    const blob = new Blob([csv], { type: "text/csv" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "adjustments_template.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div style={{ marginTop: 24 }}>
      {saveMsg && (
        <div className="alert alert-success" style={{ marginBottom: 16 }}>
          {saveMsg}
          <button className="btn btn-ghost btn-sm" style={{ marginLeft: 12 }} onClick={() => setSaveMsg("")}>Dismiss</button>
        </div>
      )}

      {errMsg && (
        <div className="alert alert-error" style={{ marginBottom: 16, whiteSpace: "pre-line" }}>
          {errMsg}
          <button className="btn btn-ghost btn-sm" style={{ marginLeft: 12 }} onClick={() => setErrMsg("")}>Dismiss</button>
        </div>
      )}

      {/* Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 8 }}>
          <select className="field-input field-select" style={{ width: 130 }} value={month} onChange={e => changeMonth(e.target.value)}>
            {MONTHS.map(m => <option key={m}>{m}</option>)}
          </select>
          <select className="field-input field-select" style={{ width: 90 }} value={year} onChange={e => changeYear(e.target.value)}>
            {["2024","2025","2026","2027"].map(y => <option key={y}>{y}</option>)}
          </select>
        </div>

        <div style={{ marginLeft: "auto", display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn btn-ghost btn-sm" onClick={downloadTemplate}>
            <i className="ti ti-download" /> Download Template
          </button>
          {canEdit && (
            <>
              <label className={`btn btn-ghost btn-sm${importing ? " disabled" : ""}`} style={{ cursor: "pointer" }}>
                <i className="ti ti-file-upload" /> {importing ? "Importing…" : "Bulk Import"}
                <input
                  ref={fileRef}
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  style={{ display: "none" }}
                  onChange={e => { if (e.target.files?.[0]) handleBulkImport(e.target.files[0]); }}
                />
              </label>
              <button className="btn btn-filled btn-sm" onClick={() => { setAddErr(""); setShowAdd(true); }}>
                <i className="ti ti-plus" /> Add Adjustment
              </button>
            </>
          )}
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>Loading…</div>
      ) : rows.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: "var(--on-variant)", border: "1.5px dashed var(--outline-v)", borderRadius: "var(--radius)" }}>
          <i className="ti ti-adjustments-alt" style={{ fontSize: 32, display: "block", marginBottom: 8 }} />
          No adjustments found.<br />
          <span style={{ fontSize: 13 }}>No adjustments for {month} {year} — add individual adjustments or bulk import via Excel.</span>
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Code</th>
                <th>Type</th>
                <th>Label</th>
                <th style={{ textAlign: "right" }}>Amount (₹)</th>
                <th>Added By</th>
                {canEdit && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.id}>
                  <td>{row.employee_name}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>{row.employee_code}</td>
                  <td><span className={`badge ${TYPE_BADGE[row.type] ?? "badge-neutral"}`}>{TYPE_LABELS[row.type] ?? row.type}</span></td>
                  <td>{row.label}</td>
                  <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                    {Number(row.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </td>
                  <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{row.created_by_name}</td>
                  {canEdit && (
                    <td>
                      <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} onClick={() => handleDelete(row.id)}>
                        <i className="ti ti-trash" />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 8, fontSize: 12, color: "var(--on-variant)" }}>
            {data && (
              <>
                Showing {(data.page - 1) * data.page_size + 1}–{Math.min(data.page * data.page_size, data.count)} of {data.count} adjustments
                {" · "}Total additions: ₹{Number(data.total_additions).toLocaleString("en-IN")}
                {" · "}Total deductions: ₹{Number(data.total_deductions).toLocaleString("en-IN")}
              </>
            )}
          </div>

          {/* Pagination — reuses the existing backend page/page_size envelope */}
          {data && data.total_pages > 1 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, marginTop: 14, flexWrap: "wrap" }}>
              <button
                className="btn btn-ghost btn-sm"
                disabled={page <= 1}
                onClick={() => setPage(p => Math.max(p - 1, 1))}
              >
                <i className="ti ti-chevron-left" /> Previous
              </button>
              {getPageNumbers(data.page, data.total_pages).map((p, i) =>
                p === "…" ? (
                  <span key={`ellipsis-${i}`} style={{ padding: "0 6px", color: "var(--on-variant)", fontSize: 12 }}>…</span>
                ) : (
                  <button
                    key={p}
                    className={`btn btn-sm ${p === data.page ? "btn-filled" : "btn-ghost"}`}
                    style={{ minWidth: 32 }}
                    disabled={p === data.page}
                    onClick={() => setPage(p)}
                  >
                    {p}
                  </button>
                ),
              )}
              <button
                className="btn btn-ghost btn-sm"
                disabled={page >= data.total_pages}
                onClick={() => setPage(p => Math.min(p + 1, data.total_pages))}
              >
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          )}
        </div>
      )}

      {showAdd && (
        <AddAdjustmentModal
          month={param}
          saving={saving}
          error={addErr}
          onClose={() => { setShowAdd(false); setAddErr(""); }}
          onSave={async (form) => {
            setSaving(true);
            setAddErr("");
            try {
              await clientApi.post(API.payroll.adjustments, form);
              reloadFromPageOne();
              setShowAdd(false);
              setSaveMsg("Adjustment added.");
            } catch (err: unknown) {
              const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Failed to save.";
              setAddErr(msg);
            } finally {
              setSaving(false);
            }
          }}
        />
      )}
    </div>
  );
}

/* ── Add Adjustment Modal ───────────────────────────────────────────────── */

interface AddForm {
  employee_code: string;
  type: string;
  label: string;
  amount: string;
}

interface AddModalProps {
  month: string;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSave: (form: { employee_code: string; type: string; label: string; amount: number; month: string }) => Promise<void>;
}

function AddAdjustmentModal({ month, saving, error, onClose, onSave }: AddModalProps) {
  const [form, setForm] = useState<AddForm>({ employee_code: "", type: "addition", label: "", amount: "" });
  const [errors, setErrors] = useState<Partial<AddForm>>({});

  function validate(): boolean {
    const e: Partial<AddForm> = {};
    if (!form.employee_code.trim()) e.employee_code = "Employee code is required";
    if (!form.label.trim())         e.label         = "Label is required";
    if (!form.amount || isNaN(Number(form.amount)) || Number(form.amount) <= 0)
      e.amount = "Enter a valid positive amount";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) return;
    await onSave({
      employee_code: form.employee_code.trim(),
      type: form.type,
      label: form.label.trim(),
      amount: Number(form.amount),
      month,
    });
  }

  return (
    <Modal
      title="Add Adjustment"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</> : <><i className="ti ti-check" /> Add</>}
          </button>
        </>
      }
    >
      {error && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" />
          <div>{error}</div>
        </div>
      )}

      <div className="field-group mb-16">
        <label className="field-label">Employee Code <span style={{ color: "var(--error)" }}>*</span></label>
        <input className="field-input" placeholder="e.g. EMP001" value={form.employee_code}
          onChange={e => { setForm(p => ({ ...p, employee_code: e.target.value })); setErrors(p => ({ ...p, employee_code: undefined })); }} />
        {errors.employee_code && <span className="field-error-msg">{errors.employee_code}</span>}
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Type <span style={{ color: "var(--error)" }}>*</span></label>
        <select className="field-input field-select" value={form.type} onChange={e => setForm(p => ({ ...p, type: e.target.value }))}>
          <option value="addition">Addition</option>
          <option value="deduction">Deduction</option>
          <option value="arrear">Arrear</option>
        </select>
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Label <span style={{ color: "var(--error)" }}>*</span></label>
        <input className="field-input" placeholder="e.g. Festival Bonus, Loan Recovery" value={form.label}
          onChange={e => { setForm(p => ({ ...p, label: e.target.value })); setErrors(p => ({ ...p, label: undefined })); }} />
        {errors.label && <span className="field-error-msg">{errors.label}</span>}
      </div>

      <div className="field-group">
        <label className="field-label">Amount (₹) <span style={{ color: "var(--error)" }}>*</span></label>
        <input className="field-input" type="number" min="1" placeholder="e.g. 5000" value={form.amount}
          onChange={e => { setForm(p => ({ ...p, amount: e.target.value })); setErrors(p => ({ ...p, amount: undefined })); }} />
        {errors.amount && <span className="field-error-msg">{errors.amount}</span>}
      </div>
    </Modal>
  );
}
