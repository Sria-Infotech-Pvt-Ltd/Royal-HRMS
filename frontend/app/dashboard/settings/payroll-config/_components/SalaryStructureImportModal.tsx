"use client";

// Payroll Configuration → Salary Structures → Import.
//   mode "structures": one row per component (Structure Name, Component,
//     Type, Calculation, Value, Role, Taxable, Order). New structures are
//     created; an existing name is updated only when "Update existing
//     structures" is ticked. Employees' saved salary revisions are never
//     changed.
//   mode "assign": Employee ID, Structure Name, Effective From — saves a new
//     salary revision (same CTC, the structure's components) per valid row.
//   mode "salaries" (Payroll → Salary Setup): one row per employee with the
//     monthly amount of each component — saves a new salary revision per row
//     (CTC = monthly earnings × 12). All or nothing; a revision with the same
//     Effective From is replaced only when "Replace …" is ticked.
// Preview first (nothing saved), explicit confirmation, and the server checks
// the whole file again before saving.

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import Modal from "@/components/Modal";
import { checkImportFile } from "@/lib/assetImport";

type Mode = "structures" | "assign" | "salaries";

interface StructurePlan {
  name: string;
  status: "create" | "update" | "no_change" | "error" | "created" | "updated";
  rows: number[];
  errors: string[];
  components: { name: string; component_type: string; calculation_type: string; value: string }[];
  changes: { added: string[]; removed: string[]; changed: string[] } | null;
  employees_following: number | null;
}
interface AssignRow {
  row: number;
  employee_id: string;
  name: string;
  structure: string;
  current_structure?: string | null;
  effective_from: string;
  status: "create" | "update" | "no_change" | "error" | "created" | "updated";
  message: string;
  // mode "salaries"
  current_ctc?: string | null;
  annual_ctc?: string | null;
  monthly_earnings?: string | null;
  components?: { name: string; amount: string; deduction: boolean }[];
}
interface Result {
  summary: Record<string, number>;
  structures?: StructurePlan[];
  rows?: AssignRow[];
}

const STATUS: Record<string, { label: string; color: string }> = {
  create:    { label: "New",            color: "var(--success, #1a7f37)" },
  created:   { label: "Created",        color: "var(--success, #1a7f37)" },
  update:    { label: "Will update",    color: "#9a6700" },
  updated:   { label: "Updated",        color: "var(--success, #1a7f37)" },
  no_change: { label: "No change",      color: "var(--on-variant)" },
  error:     { label: "Error",          color: "var(--error)" },
};

const COPY: Record<Mode, { title: string; intro: string; sample: string; url: string; sampleUrl: string }> = {
  structures: {
    title: "Import Salary Structures",
    intro: "One row per component: Structure Name, Description, Component, Type (earning / allowance / deduction), "
      + "Calculation (percentage_of_ctc / percentage_of_basic / fixed), Value, Role (basic / hra / special_allowance / other), "
      + "Taxable, Order. Each structure needs exactly one Basic. Employees' saved salary revisions are not changed.",
    sample: "salary_structure_import_sample",
    url: API.payroll.structureImport,
    sampleUrl: API.payroll.structureImportSample,
  },
  assign: {
    title: "Assign Structures to Employees",
    intro: "Columns: Employee ID, Structure Name, Effective From (YYYY-MM-DD). Each valid row saves a new salary revision "
      + "with the employee's current CTC and the structure's components — earlier revisions stay as history.",
    sample: "salary_structure_assignment_sample",
    url: API.payroll.structureAssignImport,
    sampleUrl: API.payroll.structureAssignSample,
  },
  salaries: {
    title: "Import Salaries",
    intro: "One row per employee: Employee Code, Employee Name (checked against the record), Structure Name (blank = the "
      + "branch / company default), Effective From (YYYY-MM-DD), then the monthly amount of each component of that "
      + "structure (blank = not paid), Annual CTC (optional check), PF Eligible / ESI Eligible / PT Applicable "
      + "(yes / no / blank = keep). Each row saves a new salary revision — earlier revisions stay as history and "
      + "salary structures are not changed. Nothing is saved if any row has an error.",
    sample: "salary_import_sample",
    url: API.payroll.salaryImport,
    sampleUrl: API.payroll.salaryImportSample,
  },
};

const money = (v: string | null | undefined) =>
  v == null ? "—" : `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

function apiMessage(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
}

function apiData(err: unknown): Result | null {
  return (err as { response?: { data?: { data?: Result } } })?.response?.data?.data ?? null;
}

function Badge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, color: "var(--on-variant)" };
  return <span style={{ color: s.color, fontWeight: 600, whiteSpace: "nowrap" }}>{s.label}</span>;
}

export default function SalaryStructureImportModal({ mode, onClose, onImported }: {
  mode: Mode;
  onClose: () => void;
  onImported: () => void;
}) {
  const copy = COPY[mode];
  const [file, setFile] = useState<File | null>(null);
  const [updateExisting, setUpdateExisting] = useState(false);
  const [replaceSameDate, setReplaceSameDate] = useState(false);
  const [preview, setPreview] = useState<Result | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
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
    const res = await downloadBlobFile(copy.sampleUrl, { format }, `${copy.sample}.${format}`);
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
    if (mode === "structures" && updateExisting) fd.append("update_existing", "true");
    if (mode === "salaries" && replaceSameDate) fd.append("replace_same_date", "true");
    try {
      const { data } = await clientApi.post(copy.url, fd, { headers: { "Content-Type": undefined } });
      if (dryRun) {
        setPreview(data.data);
      } else {
        setResult(data.data); setPreview(null); setConfirming(false);
        const s = data.data.summary ?? {};
        if ((s.created ?? 0) + (s.updated ?? 0) > 0) onImported();
      }
    } catch (err) {
      setConfirming(false);
      const d = apiData(err);
      if (d && !dryRun) setPreview(d);
      setErrorMsg(apiMessage(err, dryRun ? "Could not check the file." : "Import failed."));
    } finally {
      setBusy(null);
    }
  }

  const s = preview?.summary ?? {};
  const actionable = mode === "assign" ? (s.update ?? 0) : (s.create ?? 0) + (s.update ?? 0);
  const blocked = mode !== "assign" && (s.error ?? 0) > 0;   // structure and salary imports are all-or-nothing
  const unit = mode === "structures" ? "structure(s)" : "revision(s)";

  const shown = result ?? preview;

  return (
    <Modal
      title={<><i className="ti ti-file-import" style={{ marginRight: 8 }} />{copy.title}</>}
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
              {busy === "save" ? "Saving…" : `Yes, save ${actionable} ${unit}`}
            </button>
          </>
        ) : preview ? (
          <>
            <button className="btn btn-ghost" onClick={reset} disabled={!!busy}>Cancel</button>
            <button className="btn btn-filled" onClick={() => setConfirming(true)} disabled={!!busy || actionable === 0 || blocked}>
              {`Save ${actionable} ${unit}…`}
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
              {copy.intro} CSV or Excel (.xlsx), up to 1000 rows, 5 MB. Nothing is saved until you confirm.
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
            {mode === "salaries" && (
              <label style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <input type="checkbox" checked={replaceSameDate} onChange={e => setReplaceSameDate(e.target.checked)} />
                <span>
                  <strong>Replace revisions with the same Effective From</strong> — when an employee&apos;s current
                  revision starts on the same date, the imported one replaces it (the old one stays in the history).
                  Left unticked, those rows are shown as errors.
                </span>
              </label>
            )}
            {mode === "structures" && (
              <label style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <input type="checkbox" checked={updateExisting} onChange={e => setUpdateExisting(e.target.checked)} />
                <span>
                  <strong>Update existing structures</strong> with the same name — components are matched by name;
                  ones not in the file are deactivated. Affects future payroll of employees who follow the structure
                  without their own saved revision.
                </span>
              </label>
            )}
          </>
        )}

        {errorMsg && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{errorMsg}</div></div>}

        {shown && (
          <div className={`alert ${result ? "alert-success" : (s.error ?? 0) ? "alert-warn" : "alert-info"}`}>
            <i className="ti ti-list-check" />
            <div>
              {result ? "Finished: " : "Preview (nothing saved yet): "}
              {Object.entries(shown.summary).filter(([k]) => k !== "total").map(([k, v]) => `${v} ${STATUS[k]?.label.toLowerCase() ?? k}`).join(", ")}
              {` (of ${shown.summary.total}).`}
              {!result && blocked && ` Fix the errors before importing — ${mode === "structures" ? "structures" : "rows"} are imported all together.`}
            </div>
          </div>
        )}

        {confirming && preview && (
          <div className="alert alert-warn">
            <i className="ti ti-alert-triangle" />
            <div>
              {mode === "structures"
                ? `Save ${actionable} structure(s)? Updated structures change the next payroll of employees who follow them without their own saved revision (shown per structure).`
                : mode === "salaries"
                  ? `Save ${actionable} salary revision(s)? Each takes effect from its Effective From date; rows marked "Will update" replace the revision from the same date.`
                  : `Save ${actionable} new salary revision(s)? Each takes effect from its Effective From date.`}
              {" "}Every row is checked again before saving.
            </div>
          </div>
        )}

        {shown?.structures && (
          <div style={{ overflow: "auto", maxHeight: 340, border: "1px solid var(--outline-v)", borderRadius: 8 }}>
            <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
              <thead><tr><th>Structure</th><th>Status</th><th>Components</th><th>Details</th></tr></thead>
              <tbody>
                {shown.structures.map(p => (
                  <tr key={p.name}>
                    <td>{p.name}</td>
                    <td><Badge status={p.status} /></td>
                    <td>{p.components.map(c => c.name).join(", ") || "—"}</td>
                    <td style={{ color: "var(--on-variant)" }}>
                      {p.errors.length > 0 && <div style={{ color: "var(--error)" }}>{p.errors.join(" ")}</div>}
                      {p.changes && (
                        <div>
                          {p.changes.added.length > 0 && <>Added: {p.changes.added.join(", ")}. </>}
                          {p.changes.changed.length > 0 && <>Changed: {p.changes.changed.join(", ")}. </>}
                          {p.changes.removed.length > 0 && <>Deactivated: {p.changes.removed.join(", ")}. </>}
                        </div>
                      )}
                      {p.employees_following !== null && (
                        <div>{p.employees_following} employee(s) follow this structure without their own saved revision.</div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {shown?.rows && mode === "salaries" && (
          <div style={{ overflow: "auto", maxHeight: 340, border: "1px solid var(--outline-v)", borderRadius: 8 }}>
            <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
              <thead><tr><th>Row</th><th>Employee</th><th>Structure</th><th>From</th><th>Annual CTC</th><th>Monthly components</th><th>Status</th><th>Details</th></tr></thead>
              <tbody>
                {shown.rows.map(r => (
                  <tr key={r.row}>
                    <td>{r.row}</td>
                    <td>{r.name ? `${r.name} (${r.employee_id})` : r.employee_id || "—"}</td>
                    <td>{r.structure || "—"}</td>
                    <td>{r.effective_from || "—"}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {r.annual_ctc ? (r.current_ctc && r.current_ctc !== r.annual_ctc ? `${money(r.current_ctc)} → ${money(r.annual_ctc)}` : money(r.annual_ctc)) : "—"}
                    </td>
                    <td>{r.components?.length ? r.components.map(c => `${c.name}${c.deduction ? " (deduction)" : ""} ${money(c.amount)}`).join(" · ") : "—"}</td>
                    <td><Badge status={r.status} /></td>
                    <td style={{ color: r.status === "error" ? "var(--error)" : "var(--on-variant)" }}>{r.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {shown?.rows && mode === "assign" && (
          <div style={{ overflow: "auto", maxHeight: 340, border: "1px solid var(--outline-v)", borderRadius: 8 }}>
            <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
              <thead><tr><th>Row</th><th>Employee</th><th>Structure</th><th>From</th><th>Status</th><th>Details</th></tr></thead>
              <tbody>
                {shown.rows.map(r => (
                  <tr key={r.row}>
                    <td>{r.row}</td>
                    <td>{r.name ? `${r.name} (${r.employee_id})` : r.employee_id || "—"}</td>
                    <td>{r.current_structure && r.current_structure !== r.structure ? `${r.current_structure} → ${r.structure}` : r.structure}</td>
                    <td>{r.effective_from}</td>
                    <td><Badge status={r.status} /></td>
                    <td style={{ color: "var(--on-variant)" }}>{r.status === "error" || r.status === "no_change" ? r.message : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Modal>
  );
}
