"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { EmployeeSalaryConfig, SalaryStructureListItem } from "@/types/payroll";

interface PagedResponse<T> { results: T[]; count: number; }
interface Employee { id: string; full_name: string; employee_id: string; department: string; branch: string; }

interface SalaryModalState {
  employee: Employee;
  current: EmployeeSalaryConfig | null;
  annual_ctc: string;
  salary_structure: string;
  effective_from: string;
}

const fmt = (n: number | string) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

export default function SalarySetupTab() {
  const { data: salaryPage, loading: salaryLoading, refetch: refetchSalaries } =
    useFetch<PagedResponse<EmployeeSalaryConfig>>(API.payroll.employeeSalary);
  const { data: structures } = useFetch<SalaryStructureListItem[]>(API.payroll.structures);
  const { data: employeePage } = useFetch<PagedResponse<Employee>>(API.employees.list);

  const [modal, setModal] = useState<SalaryModalState | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const salaryConfigs = salaryPage?.results ?? [];
  const allEmployees = employeePage?.results ?? [];

  const configById = new Map(salaryConfigs.map(c => [c.employee, c]));

  const filteredEmployees = allEmployees.filter(emp =>
    emp.full_name.toLowerCase().includes(search.toLowerCase()) ||
    emp.employee_id.toLowerCase().includes(search.toLowerCase()) ||
    emp.department.toLowerCase().includes(search.toLowerCase())
  );

  const withCTC    = filteredEmployees.filter(e => configById.has(e.id));
  const withoutCTC = filteredEmployees.filter(e => !configById.has(e.id));

  function openModal(employee: Employee) {
    const current = configById.get(employee.id) ?? null;
    setModal({
      employee,
      current,
      annual_ctc: current ? String(current.annual_ctc) : "",
      salary_structure: current?.salary_structure ?? "",
      effective_from: current?.effective_from ?? new Date().toISOString().split("T")[0],
    });
  }

  function flash(text: string) {
    setMsg(text);
    setTimeout(() => setMsg(null), 3000);
  }

  async function save() {
    if (!modal || !modal.annual_ctc) return;
    setSaving(true);
    try {
      await clientApi.post(API.payroll.employeeSalary, {
        employee: modal.employee.id,
        annual_ctc: modal.annual_ctc,
        salary_structure: modal.salary_structure || null,
        effective_from: modal.effective_from,
      });
      setModal(null);
      refetchSalaries();
      flash("Salary config saved.");
    } catch {
      flash("Failed to save salary config.");
    } finally {
      setSaving(false);
    }
  }

  const totalWithCTC = salaryConfigs.length;
  const totalEmployees = allEmployees.length;

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
        <div className={`alert ${msg.startsWith("Failed") ? "alert-error" : "alert-success"}`}>
          <i className={`ti ${msg.startsWith("Failed") ? "ti-alert-circle" : "ti-circle-check"}`} />
          {msg}
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
                onChange={e => setSearch(e.target.value)}
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
                {withoutCTC.length} employee{withoutCTC.length !== 1 ? "s" : ""} without CTC — assign before running payroll
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
                  {withCTC.length} employee{withCTC.length !== 1 ? "s" : ""} configured
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

        {salaryLoading && (
          <div style={{ padding: "24px", textAlign: "center", color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2" style={{ fontSize: 20, display: "block", marginBottom: 8 }} />
            Loading…
          </div>
        )}

        {!salaryLoading && filteredEmployees.length === 0 && (
          <div style={{ padding: "24px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
            No employees found
          </div>
        )}
      </div>

      {/* Assign / Edit CTC modal */}
      {modal && (
        <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && setModal(null)}>
          <div className="modal" style={{ maxWidth: 480 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <i className="ti ti-currency-rupee" style={{ marginRight: 8 }} />
                {modal.current ? "Update CTC" : "Assign CTC"} — {modal.employee.full_name}
              </div>
              <button className="modal-close" onClick={() => setModal(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
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
                  <input
                    type="date"
                    className="field-input"
                    value={modal.effective_from}
                    onChange={e => setModal(m => m ? { ...m, effective_from: e.target.value } : m)}
                  />
                </div>
              </div>

              <div className="field-group">
                <label className="field-label">Salary Structure Override</label>
                <select
                  className="field-input"
                  value={modal.salary_structure}
                  onChange={e => setModal(m => m ? { ...m, salary_structure: e.target.value } : m)}
                >
                  <option value="">— Use branch / company default —</option>
                  {(structures ?? []).filter(s => s.is_active).map(s => (
                    <option key={s.id} value={s.id}>{s.name}{s.is_default ? " (Default)" : ""}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setModal(null)}>Cancel</button>
              <button
                className="btn btn-filled"
                onClick={save}
                disabled={saving || !modal.annual_ctc || !modal.effective_from}
              >
                {saving ? <><i className="ti ti-loader-2 animate-spin" /> Saving…</> : <><i className="ti ti-check" /> Save CTC</>}
              </button>
            </div>
          </div>
        </div>
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
            <th>Department</th>
            <th>Branch</th>
            <th style={{ textAlign: "right" }}>Annual CTC</th>
            <th style={{ textAlign: "right" }}>Monthly CTC</th>
            <th>Effective From</th>
            <th>Structure</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {employees.map(emp => {
            const config = configById.get(emp.id);
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
