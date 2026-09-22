"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useDepartmentOptions } from "@/hooks/useDepartmentOptions";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import BranchFilterSelect from "@/components/BranchFilterSelect";
import type { PaginatedUnpunches } from "@/types/attendance";

interface BranchOption { id: number; branch_name: string }

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export default function UnpunchesTab() {
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);

  const [branchInput, setBranchInput] = useState("");
  const [department, setDepartment]   = useState("");
  const [date, setDate]               = useState(new Date().toISOString().split("T")[0]);
  const [page, setPage]               = useState(1);

  const branch = unrestricted ? branchInput : effectiveBranch;

  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(
    unrestricted ? `${API.branches.list}?page_size=100` : null
  );
  const branches    = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);
  const departments = useDepartmentOptions(unrestricted, effectiveBranch);

  const listUrl = user
    ? `${API.attendance.unPunches}${toQuery({ date, branch, department, page, page_size: 20 })}`
    : null;
  const { data, loading, error } = useFetch<PaginatedUnpunches>(listUrl);
  const rows = data?.results ?? [];

  return (
    <>
      <div className="alert alert-warn mb-16">
        <i className="ti ti-alert-triangle" />
        <span>
          Employees who clocked in but never clocked out (past shift end + grace period) for the selected date.
        </span>
      </div>

      <div className="filter-bar" style={{ marginBottom: 14 }}>
        <input
          type="date"
          className="field-input"
          style={{ width: 160 }}
          value={date}
          onChange={e => { setDate(e.target.value); setPage(1); }}
        />
        <BranchFilterSelect
          branches={branches}
          value={branchInput}
          onChange={value => { setBranchInput(value); setPage(1); }}
          locked={!unrestricted}
          lockedBranchName={effectiveBranch}
        />
        <select className="field-input field-select" style={{ width: 180 }} value={department} onChange={e => { setDepartment(e.target.value); setPage(1); }}>
          <option value="">All Org Units</option>
          {departments.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee ID</th>
                <th>Name</th>
                <th>Company Code</th>
                <th>Date</th>
                <th>Clock In</th>
                <th>Expected Out</th>
                <th>Correction Status</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={7} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>No un-punches found for this date.</td></tr>
              )}
              {rows.map(r => (
                <tr key={`${r.employee_id}-${r.date}`}>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.employee_id}</td>
                  <td>{r.name}</td>
                  <td>{r.branch}</td>
                  <td>{r.date}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.clock_in}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: "var(--on-variant)" }}>{r.expected_out}</td>
                  <td>
                    {r.correction_pending
                      ? <span className="badge badge-warn">Correction Submitted</span>
                      : <span className="badge badge-neutral">No Correction Filed</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data && data.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {data.page} of {data.total_pages}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= data.total_pages} onClick={() => setPage(p => Math.min(p + 1, data.total_pages))}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
