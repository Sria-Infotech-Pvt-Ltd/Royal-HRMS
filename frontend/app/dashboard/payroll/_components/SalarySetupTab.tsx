"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useSalarySetup } from "@/hooks/useSalarySetup";
import { API } from "@/lib/api/endpoints";
import type { SalaryStructureListItem } from "@/types/payroll";
import type { SalarySetupFilter, SalarySetupRow } from "@/types/salarySetup";
import SalaryAssignModal from "./SalaryAssignModal";
import SalarySetupTable from "./SalarySetupTable";

const FILTERS: { value: SalarySetupFilter; label: string }[] = [
  { value: "all", label: "Everyone" },
  { value: "missing", label: "CTC missing" },
  { value: "configured", label: "CTC configured" },
  { value: "blocked", label: "Not payroll ready" },
  { value: "ready", label: "Payroll ready" },
];

export default function SalarySetupTab() {
  const { list, summary, search, setSearch, status, changeStatus, page, setPage, save } = useSalarySetup();
  const { data: structures } = useFetch<SalaryStructureListItem[]>(API.payroll.structures);
  const [editing, setEditing] = useState<SalarySetupRow | null>(null);
  const [message, setMessage] = useState<{ text: string; isError: boolean } | null>(null);

  const rows = list.data?.results ?? [];
  const totals = summary.data;

  function flash(text: string, isError = false) {
    setMessage({ text, isError });
    setTimeout(() => setMessage(null), isError ? 5000 : 3500);
  }

  async function saveSalary(values: { annual_ctc: string; effective_from: string; salary_structure: string | null }) {
    if (!editing) return;
    const result = await save({ employee: editing.uuid, ...values });
    setEditing(null);
    flash(result.message);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="stats-grid" style={{ marginBottom: 0 }}>
        <div className="stat-card"><div className="stat-label">Total Employees</div><div className="stat-value">{totals?.total ?? "—"}</div><div className="stat-sub">Active in system</div></div>
        <div className="stat-card">
          <div className="stat-label">CTC Configured</div>
          <div className="stat-value" style={{ color: "var(--success)" }}>{totals?.configured ?? "—"}</div>
          <div className="stat-sub">{totals?.scheduled ? `${totals.scheduled} start later` : "Have a salary record"}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">CTC Missing</div>
          <div className="stat-value" style={{ color: (totals?.missing ?? 0) > 0 ? "var(--warn)" : "var(--success)" }}>{totals?.missing ?? "—"}</div>
          <div className="stat-sub">Employees need setup</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Payroll Ready</div>
          <div className="stat-value" style={{ color: "var(--success)" }}>{totals?.payroll_ready ?? "—"}</div>
          <div className="stat-sub">{totals ? `${totals.blocked} not ready` : ""}</div>
        </div>
      </div>

      {totals && totals.blocked > 0 && (
        <div className="alert alert-info" style={{ marginBottom: 0 }}>
          <i className="ti ti-info-circle" />
          <span>
            Payroll ready needs: {totals.requirements.join("; ")}. Blocked: {totals.blocked_by.no_salary_record} without a current salary record,{" "}
            {totals.blocked_by.no_salary_structure} without a salary structure, {totals.blocked_by.no_bank_details} without bank details.
          </span>
        </div>
      )}

      {message && <div className={`alert ${message.isError ? "alert-error" : "alert-success"}`}><i className={`ti ${message.isError ? "ti-alert-circle" : "ti-circle-check"}`} />{message.text}</div>}
      {list.error && <div className="alert alert-error" role="alert">{list.error}</div>}

      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-currency-rupee" /> Employee Salary Configuration</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <select className="field-input field-select" style={{ width: 170 }} value={status} onChange={event => changeStatus(event.target.value as SalarySetupFilter)} aria-label="Filter employees">
              {FILTERS.map(filter => <option key={filter.value} value={filter.value}>{filter.label}</option>)}
            </select>
            <div style={{ position: "relative" }}>
              <i className="ti ti-search" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--on-variant)", fontSize: 14 }} />
              <input type="text" placeholder="Search employees…" value={search} onChange={event => setSearch(event.target.value)} className="field-input" style={{ paddingLeft: 32, width: 220 }} aria-label="Search employees" />
            </div>
          </div>
        </div>

        {list.loading && <div style={{ padding: 24, textAlign: "center", color: "var(--on-variant)" }}><i className="ti ti-loader-2 animate-spin" /> Loading…</div>}
        {!list.loading && rows.length === 0 && <div style={{ padding: 24, textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>No employees found.</div>}
        {rows.length > 0 && <SalarySetupTable rows={rows} onEdit={setEditing} />}

        {list.data && list.data.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {list.data.page} of {list.data.total_pages} · {list.data.count} employees</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}><i className="ti ti-chevron-left" /> Prev</button>
              <button className="btn btn-ghost btn-sm" type="button" disabled={page >= list.data.total_pages} onClick={() => setPage(page + 1)}>Next <i className="ti ti-chevron-right" /></button>
            </div>
          </div>
        )}
      </div>

      {editing && <SalaryAssignModal employee={editing} structures={structures ?? []} onClose={() => setEditing(null)} onSave={saveSalary} />}
    </div>
  );
}
