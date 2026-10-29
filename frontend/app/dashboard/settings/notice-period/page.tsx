"use client";

// Settings → Notice Period: each employee's assigned notice period (calendar
// days). Uses the employee list API (same branch / team scope as the Employees
// page) and saves through the employee update API, which needs
// employees.edit and records the change in the audit log.

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { formatNoticePeriod, noticePeriodInputError } from "@/lib/noticePeriod";

interface EmployeeRow {
  employee_id: string;
  full_name: string;
  branch: string;
  department: string;
  designation: string;
  notice_period_days: number | null;
}

interface EmployeePage { count: number; results: EmployeeRow[] }

const PAGE_SIZE = 20;

function toQuery(params: Record<string, string | number>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== "" && v !== undefined) q.append(k, String(v)); });
  return `?${q.toString()}`;
}

export default function NoticePeriodSettingsPage() {
  const canEdit = usePermission("employees.edit");
  const [search, setSearch]         = useState("");
  const [debounced, setDebounced]   = useState("");
  const [department, setDepartment] = useState("");
  const [page, setPage]             = useState(1);

  useEffect(() => {
    const t = setTimeout(() => { setDebounced(search.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const { data, loading, error, refetch } = useFetch<EmployeePage>(
    // No status filter: onboarding employees (e.g. just imported) need a notice period too.
    `${API.employees.list}${toQuery({ search: debounced, department, page, page_size: PAGE_SIZE })}`,
  );
  const rows = data?.results ?? [];
  const pages = Math.max(1, Math.ceil((data?.count ?? 0) / PAGE_SIZE));
  const departments = [...new Set(rows.map(r => r.department).filter(Boolean))].sort();

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Notice Period</div>
          <div className="page-sub">Assign each employee&apos;s notice period — used for the expected last working day when they resign</div>
        </div>
      </div>

      <div className="filter-bar" style={{ marginBottom: 14 }}>
        <input className="field-input" style={{ width: 260 }} placeholder="Search name or employee ID"
          value={search} onChange={e => setSearch(e.target.value)} aria-label="Search employees" />
        <select className="field-input" style={{ width: 200 }} value={department}
          onChange={e => { setDepartment(e.target.value); setPage(1); }} aria-label="Department">
          <option value="">All Departments</option>
          {departments.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{data?.count ?? 0} employees</span>
      </div>

      {!canEdit && (
        <div className="alert alert-info mb-16">You can view notice periods. Changing them needs permission to edit employees.</div>
      )}
      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Employee ID</th><th>Name</th><th>Branch</th><th>Department</th><th>Designation</th><th>Notice Period</th></tr>
            </thead>
            <tbody>
              {loading && rows.length === 0 && <tr><td colSpan={6}>Loading…</td></tr>}
              {!loading && rows.length === 0 && <tr><td colSpan={6}>No employees found.</td></tr>}
              {rows.map(r => <NoticeRow key={r.employee_id} row={r} canEdit={canEdit} onSaved={refetch} />)}
            </tbody>
          </table>
        </div>
      </div>

      {pages > 1 && (
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 12, alignItems: "center" }}>
          <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</button>
          <span style={{ fontSize: 12 }}>Page {page} of {pages}</span>
          <button className="btn btn-ghost btn-sm" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}

function NoticeRow({ row, canEdit, onSaved }: { row: EmployeeRow; canEdit: boolean; onSaved: () => void }) {
  const initial = row.notice_period_days === null ? "" : String(row.notice_period_days);
  const [value, setValue]   = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState<string | null>(null);
  const [saved, setSaved]   = useState(false);
  const dirty = value.trim() !== initial;

  async function save() {
    const problem = noticePeriodInputError(value);
    if (problem) { setError(problem); return; }
    setSaving(true); setError(null); setSaved(false);
    try {
      await clientApi.put(API.employees.detail(row.employee_id), {
        notice_period_days: value.trim() === "" ? null : Number(value.trim()),
      });
      setSaved(true);
      onSaved();
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Could not save.");
    } finally { setSaving(false); }
  }

  return (
    <tr>
      <td>{row.employee_id}</td>
      <td>{row.full_name}</td>
      <td>{row.branch || "—"}</td>
      <td>{row.department || "—"}</td>
      <td>{row.designation || "—"}</td>
      <td style={{ minWidth: 220 }}>
        {canEdit ? (
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input className="field-input" style={{ width: 80 }} inputMode="numeric" placeholder="days"
              value={value} onChange={e => { setValue(e.target.value); setSaved(false); }}
              aria-label={`Notice period for ${row.full_name}`} />
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>days</span>
            <button className="btn btn-filled btn-sm" disabled={!dirty || saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
            {saved && !dirty && <i className="ti ti-circle-check" style={{ color: "var(--success)" }} aria-label="Saved" />}
          </div>
        ) : formatNoticePeriod(row.notice_period_days)}
        {error && <div className="field-error" role="alert">{error}</div>}
      </td>
    </tr>
  );
}
