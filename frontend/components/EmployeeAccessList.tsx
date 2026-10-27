"use client";

// Every employee with how many permissions they hold, so you can see who has what at a glance. Pick a row to
// see or change that person's access.

import { useEmployeeAccessList, type AccessFilter } from "@/hooks/useEmployeeAccessList";
import type { EmployeeAccessRow } from "@/types/orgStructure";

const ACCESS_OPTIONS: { value: AccessFilter; label: string }[] = [
  { value: "", label: "Everyone" },
  { value: "extra", label: "Has extra access" },
  { value: "superuser", label: "Superusers" },
  { value: "no_seat", label: "No position" },
];

interface Props {
  onSelect: (row: EmployeeAccessRow) => void;
}

export default function EmployeeAccessList({ onSelect }: Props) {
  const { list, branchOptions, filters, setSearch, setBranch, setAccess, setPage } = useEmployeeAccessList();
  const rows = list.data?.results ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <input className="finput w-64" type="search" value={filters.search} onChange={event => setSearch(event.target.value)} placeholder="Search name, email or ID" aria-label="Search employees" />
        <select className="finput w-48" value={filters.branch} onChange={event => setBranch(event.target.value)} aria-label="Filter by branch">
          <option value="">All branches</option>
          {branchOptions.map(branch => <option key={branch.id} value={branch.branch_name}>{branch.branch_name}</option>)}
        </select>
        <select className="finput w-48" value={filters.access} onChange={event => setAccess(event.target.value as AccessFilter)} aria-label="Filter by access">
          {ACCESS_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        {list.data && <span className="ml-auto text-sm text-[var(--on-variant)]">{list.data.count} employee{list.data.count === 1 ? "" : "s"}</span>}
      </div>

      {list.error && <div className="alert alert-error" role="alert">{list.error}</div>}

      <div className="overflow-x-auto rounded-xl border border-[var(--outline-v)]">
        <table className="w-full min-w-[760px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-[var(--outline-v)] bg-[var(--bg-low)] text-left text-[11px] font-bold uppercase tracking-[0.06em] text-[var(--on-variant)]">
              <th className="px-4 py-3">Employee</th>
              <th className="px-3 py-3">Position</th>
              <th className="px-3 py-3">Branch</th>
              <th className="px-3 py-3 text-right">Permissions</th>
              <th className="px-3 py-3 text-right">From position</th>
              <th className="px-3 py-3 text-right">Extra</th>
              <th className="px-3 py-3" />
            </tr>
          </thead>
          <tbody>
            {list.loading && <tr><td colSpan={7} className="px-4 py-8 text-center text-[var(--on-variant)]">Loading…</td></tr>}
            {!list.loading && rows.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-[var(--on-variant)]">No employee matches those filters.</td></tr>}
            {rows.map(row => (
              <tr key={row.uuid} className="cursor-pointer border-b border-[var(--outline-v)] last:border-b-0 hover:bg-[var(--bg-low)]" onClick={() => onSelect(row)}>
                <td className="px-4 py-2.5">
                  <div className="font-medium text-[var(--on-bg)]">{row.full_name}</div>
                  <div className="text-xs text-[var(--on-variant)]">{row.employee_id}</div>
                </td>
                <td className="px-3 py-2.5 text-[var(--on-variant)]">{row.position || "—"}</td>
                <td className="px-3 py-2.5 text-[var(--on-variant)]">{row.branch || "—"}</td>
                <td className="px-3 py-2.5 text-right font-semibold text-[var(--on-bg)]">
                  {row.total}
                  {row.is_superuser && <span className="ml-2 rounded-full bg-[var(--sec-c)] px-2 py-0.5 text-[11px] font-semibold text-[var(--primary)]">All · Superuser</span>}
                </td>
                <td className="px-3 py-2.5 text-right text-[var(--on-variant)]">{row.is_superuser ? "—" : row.from_seat}</td>
                <td className="px-3 py-2.5 text-right text-[var(--on-variant)]">{row.is_superuser ? "—" : row.extra}</td>
                <td className="px-3 py-2.5 text-right">
                  <button type="button" className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={event => { event.stopPropagation(); onSelect(row); }}>
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {list.data && list.data.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm text-[var(--on-variant)]">
          <span>Page {list.data.page} of {list.data.total_pages}</span>
          <div className="flex gap-2">
            <button type="button" className="btn btn-ghost btn-sm" disabled={filters.page <= 1} onClick={() => setPage(filters.page - 1)}>Previous</button>
            <button type="button" className="btn btn-ghost btn-sm" disabled={filters.page >= list.data.total_pages} onClick={() => setPage(filters.page + 1)}>Next</button>
          </div>
        </div>
      )}
    </div>
  );
}
