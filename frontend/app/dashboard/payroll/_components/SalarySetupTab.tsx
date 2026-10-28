"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { EmployeeSalaryConfig, SalaryStructureListItem } from "@/types/payroll";
import DateInput from "@/components/shared/DateInput";

interface PagedResponse<T> { results: T[]; count: number; page: number; total_pages: number; }
interface Employee { id: string; uuid: string; full_name: string; employee_id: string; department: string; branch: string; }

interface SalaryModalState {
  employee: Employee;
  current: EmployeeSalaryConfig | null;
  annual_ctc: string;
  salary_structure: string;
  effective_from: string;
}

const fmt = (n: number | string) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

// UAT-019 — both this screen's KPI cards and its employee table used to come
// from the SAME page-1-only fetch of two independently-paginated endpoints
// (20 of 52 employees, 20 of 52 configs), so "Total"/"Configured" never
// matched the real counts and most employees never appeared at all.
// Employees drive real server-side pagination + search below; salary configs
// are fetched in one page at PAGE_SIZE_CAP (the system's own designed
// ceiling for a single request — see core/pagination.py's max_page_size)
// purely to build the Set/Not-Set lookup, never for a displayed count.
const EMPLOYEE_PAGE_SIZE = 20;
const PAGE_SIZE_CAP      = 100;

export default function SalarySetupTab() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const { data: salaryPage, refetch: refetchSalaries } =
    useFetch<PagedResponse<EmployeeSalaryConfig>>(`${API.payroll.employeeSalary}?page_size=${PAGE_SIZE_CAP}`);
  const { data: structures } = useFetch<SalaryStructureListItem[]>(API.payroll.structures);
  const { data: employeePage, loading: employeesLoading } = useFetch<PagedResponse<Employee>>(
    `${API.employees.list}?page=${page}&page_size=${EMPLOYEE_PAGE_SIZE}&search=${encodeURIComponent(search)}`,
  );

  const [modal, setModal] = useState<SalaryModalState | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ text: string; isError: boolean } | null>(null);
  const [modalErr, setModalErr] = useState<string | null>(null);

  const salaryConfigs = salaryPage?.results ?? [];
  const filteredEmployees = employeePage?.results ?? [];

  const configById = new Map(salaryConfigs.map(c => [c.employee, c]));

  const withCTC    = filteredEmployees.filter(e => configById.has(e.uuid));
  const withoutCTC = filteredEmployees.filter(e => !configById.has(e.uuid));

  function changeSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  function openModal(employee: Employee) {
    const current = configById.get(employee.uuid) ?? null;
    setModalErr(null);
    setModal({
      employee,
      current,
      annual_ctc: current ? String(current.annual_ctc) : "",
      salary_structure: current?.salary_structure ?? "",
      effective_from: current?.effective_from ?? new Date().toISOString().split("T")[0],
    });
  }

  function flash(text: string, isError = false) {
    setMsg({ text, isError });
    setTimeout(() => setMsg(null), isError ? 5000 : 3000);
  }

  async function save() {
    if (!modal) return;
    setModalErr(null);
    if (!modal.annual_ctc) { setModalErr("Annual CTC is required."); return; }
    const ctc = Number(modal.annual_ctc);
    if (Number.isNaN(ctc) || ctc <= 0) { setModalErr("Annual CTC must be greater than 0."); return; }
    setSaving(true);
    try {
      await clientApi.post(API.payroll.employeeSalary, {
        employee: modal.employee.uuid,
        annual_ctc: modal.annual_ctc,
        salary_structure: modal.salary_structure || null,
        effective_from: modal.effective_from,
      });
      setModal(null);
      refetchSalaries();
      flash("Salary config saved.");
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message || "Failed to save salary config.";
      setModalErr(message);
    } finally {
      setSaving(false);
    }
  }

  // The single count source the recommendation asked for — paginator totals,
  // never results.length (which only ever reflected one page).
  const totalEmployees = employeePage?.count ?? 0;
  const totalWithCTC   = salaryPage?.count ?? 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Summary row */}
      <div className="stats-grid" style={{ marginBottom: 0 }}>
        <div className="stat-card">
          <div className="stat-label">Total Employees</div>
          <div className="stat-value">{totalEmployees}</div>
          <div className="stat-sub">Active in system</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">CTC Configured</div>
          <div className="stat-value" style={{ color: "var(--success)" }}>{totalWithCTC}</div>
          <div className="stat-sub">Ready for payroll</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">CTC Missing</div>
          <div className="stat-value" style={{ color: totalEmployees - totalWithCTC > 0 ? "var(--warn)" : "var(--success)" }}>
            {totalEmployees - totalWithCTC}
          </div>
          <div className="stat-sub">Employees need setup</div>
        </div>
      </div>

      {msg && (
        <div className={`alert ${msg.isError ? "alert-error" : "alert-success"}`}>
          <i className={`ti ${msg.isError ? "ti-alert-circle" : "ti-circle-check"}`} />
          {msg.text}
        </div>
      )}

      {/* Search */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-currency-rupee" /> Employee Salary Configuration</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ position: "relative" }}>
              <i className="ti ti-search" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--on-variant)", fontSize: 14 }} />
              <input
                type="text"
                placeholder="Search employees…"
                value={search}
                onChange={e => changeSearch(e.target.value)}
                className="field-input"
                style={{ paddingLeft: 32, width: 220 }}
              />
            </div>
          </div>
        </div>

        {/* Employees missing CTC — shown at top with warning */}
        {withoutCTC.length > 0 && (
          <>
            <div style={{ padding: "10px 20px 6px", borderTop: "1px solid var(--outline-v)", display: "flex", alignItems: "center", gap: 8 }}>
              <i className="ti ti-alert-circle" style={{ color: "var(--warn)", fontSize: 15 }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--warn)" }}>
                Without CTC on this page — assign before running payroll ({totalEmployees - totalWithCTC} missing in total)
              </span>
            </div>
            <EmployeeTable
              employees={withoutCTC}
              configById={configById}
              onEdit={openModal}
              highlight="warn"
            />
          </>
        )}

        {/* Employees with CTC */}
        {withCTC.length > 0 && (
          <>
            {withoutCTC.length > 0 && (
              <div style={{ padding: "10px 20px 6px", borderTop: "1px solid var(--outline-v)", display: "flex", alignItems: "center", gap: 8 }}>
                <i className="ti ti-circle-check" style={{ color: "var(--success)", fontSize: 15 }} />
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--success)" }}>
                  Configured on this page
                </span>
              </div>
            )}
            <EmployeeTable
              employees={withCTC}
              configById={configById}
              onEdit={openModal}
              highlight="none"
            />
          </>
        )}

        {employeesLoading && (
          <div style={{ padding: "24px", textAlign: "center", color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2" style={{ fontSize: 20, display: "block", marginBottom: 8 }} />
            Loading…
          </div>
        )}

        {!employeesLoading && filteredEmployees.length === 0 && (
          <div style={{ padding: "24px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
            No employees found
          </div>
        )}

        {employeePage && employeePage.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Page {employeePage.page} of {employeePage.total_pages} · {totalEmployees} employees
            </span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= employeePage.total_pages} onClick={() => setPage(p => Math.min(employeePage.total_pages, p + 1))}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Assign / Edit CTC modal */}
      {modal && (
        <Modal
          title={
            <>
              <i className="ti ti-currency-rupee" style={{ marginRight: 8 }} />
              {modal.current ? "Update CTC" : "Assign CTC"} — {modal.employee.full_name}
            </>
          }
          onClose={() => setModal(null)}
          maxWidth={480}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setModal(null)}>Cancel</button>
              <button
                className="btn btn-filled"
                onClick={save}
                disabled={saving || !modal.annual_ctc || !modal.effective_from}
              >
                {saving ? <><i className="ti ti-loader-2 animate-spin" /> Saving…</> : <><i className="ti ti-check" /> Save CTC</>}
              </button>
            </>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {modalErr && (
              <div className="alert alert-error" style={{ marginBottom: 0 }}>
                <i className="ti ti-alert-circle" />
                <span>{modalErr}</span>
              </div>
            )}
            <div style={{ padding: "10px 14px", background: "var(--bg-low)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--on-variant)" }}>
              <strong>{modal.employee.employee_id}</strong> · {modal.employee.department} · {modal.employee.branch}
            </div>

            {modal.current && (
              <div className="alert alert-info" style={{ marginBottom: 0 }}>
                <i className="ti ti-info-circle" />
                <span>Current CTC: <strong>{fmt(modal.current.annual_ctc)}/year</strong> (effective {modal.current.effective_from}). Saving will deactivate this and create a new record.</span>
              </div>
            )}

            <div className="form-row cols-2">
              <div className="field-group">
                <label className="field-label">Annual CTC (₹) *</label>
                <input
                  type="number"
                  className="field-input"
                  min={0}
                  step={1000}
                  placeholder="e.g. 600000"
                  value={modal.annual_ctc}
                  onChange={e => setModal(m => m ? { ...m, annual_ctc: e.target.value } : m)}
                />
                {modal.annual_ctc && (
                  <span style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4, display: "block" }}>
                    Monthly: {fmt(Number(modal.annual_ctc) / 12)}
                  </span>
                )}
              </div>
              <div className="field-group">
                <label className="field-label">Effective From *</label>
                <DateInput className="field-input" value={modal.effective_from} onChange={isoDate => setModal(m => m ? { ...m, effective_from: isoDate } : m)} />
              </div>
            </div>

            <div className="field-group">
              <label className="field-label">Salary Structure Override</label>
              <select
                className="field-input field-select"
                value={modal.salary_structure}
                onChange={e => setModal(m => m ? { ...m, salary_structure: e.target.value } : m)}
              >
                <option value="">— Use Company Code / company default —</option>
                {(structures ?? []).filter(s => s.is_active).map(s => (
                  <option key={s.id} value={s.id}>{s.name}{s.is_default ? " (Default)" : ""}</option>
                ))}
              </select>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Sub-component ──────────────────────────────────────────────────────────────

function EmployeeTable({
  employees,
  configById,
  onEdit,
  highlight,
}: {
  employees: Employee[];
  configById: Map<string, EmployeeSalaryConfig>;
  onEdit: (e: Employee) => void;
  highlight: "warn" | "none";
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Employee</th>
            <th>Org Unit</th>
            <th>Company Code</th>
            <th style={{ textAlign: "right" }}>Annual CTC</th>
            <th style={{ textAlign: "right" }}>Monthly CTC</th>
            <th>Effective From</th>
            <th>Structure</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {employees.map(emp => {
            const config = configById.get(emp.uuid);
            return (
              <tr key={emp.id} style={highlight === "warn" ? { background: "var(--warn-c)" } : {}}>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, flexShrink: 0 }}>
                      {emp.full_name.charAt(0)}
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{emp.full_name}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{emp.employee_id}</div>
                    </div>
                  </div>
                </td>
                <td style={{ fontSize: 13 }}>{emp.department || "—"}</td>
                <td style={{ fontSize: 13 }}>{emp.branch || "—"}</td>
                <td style={{ textAlign: "right", fontWeight: 600 }}>
                  {config ? fmt(config.annual_ctc) : <span style={{ color: "var(--warn)", fontSize: 12 }}>Not set</span>}
                </td>
                <td style={{ textAlign: "right", fontSize: 13, color: "var(--on-variant)" }}>
                  {config ? fmt(config.monthly_ctc) : "—"}
                </td>
                <td style={{ fontSize: 12, color: "var(--on-variant)" }}>
                  {config?.effective_from ?? "—"}
                </td>
                <td style={{ fontSize: 12, color: "var(--on-variant)" }}>
                  {config?.structure_name ?? "Default"}
                </td>
                <td>
                  <button className="btn btn-ghost btn-sm" onClick={() => onEdit(emp)}>
                    <i className={`ti ${config ? "ti-edit" : "ti-plus"}`} />
                    {config ? " Edit" : " Assign"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
