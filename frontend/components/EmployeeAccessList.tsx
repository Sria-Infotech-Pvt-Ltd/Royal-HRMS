"use client";

// Every employee with how many permissions they hold, so you can see who has what at a glance. Pick a row to
// see or change that person's access.

import { useEmployeeAccessList, type AccessFilter } from "@/hooks/useEmployeeAccessList";
import { accessShare, hueOf, initialsOf } from "@/lib/accessListView";
import type { EmployeeAccessRow } from "@/types/orgStructure";

const ACCESS_OPTIONS: { value: AccessFilter; label: string; icon: string }[] = [
  { value: "", label: "Everyone", icon: "ti-users" },
  { value: "extra", label: "Has extra access", icon: "ti-user-plus" },
  { value: "superuser", label: "Superusers", icon: "ti-crown" },
  { value: "no_seat", label: "No position", icon: "ti-user-question" },
];

const SEGMENT_COLORS = { everyone: "var(--outline-v)", position: "var(--primary-c)", extra: "var(--primary)" } as const;

interface Props {
  onSelect: (row: EmployeeAccessRow) => void;
}

function Avatar({ name }: { name: string }) {
  const hue = hueOf(name);
  return (
    <span
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold"
      style={{ background: `hsl(${hue} 70% 90%)`, color: `hsl(${hue} 45% 32%)` }}
      aria-hidden="true"
    >
      {initialsOf(name)}
    </span>
  );
}

/** A bar split into what everyone gets, what the position adds and what was given personally. */
function ShareBar({ row }: { row: EmployeeAccessRow }) {
  const share = row.is_superuser ? { everyone: 0, position: 0, extra: 100 } : accessShare(row);
  return (
    <span
      className="flex h-1.5 w-28 overflow-hidden rounded-full" style={{ background: "var(--outline-v)" }}
      title={row.is_superuser ? "Every permission" : `Everyone ${row.from_baseline} · Position ${row.from_seat} · Extra ${row.extra}`}
    >
      <span style={{ width: `${share.everyone}%`, background: SEGMENT_COLORS.everyone, filter: "brightness(.85)" }} />
      <span style={{ width: `${share.position}%`, background: SEGMENT_COLORS.position }} />
      <span style={{ width: `${share.extra}%`, background: SEGMENT_COLORS.extra }} />
    </span>
  );
}

function Badge({ children, tone }: { children: React.ReactNode; tone: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ background: `color-mix(in srgb, ${tone} 14%, transparent)`, color: tone }}>
      {children}
    </span>
  );
}

export default function EmployeeAccessList({ onSelect }: Props) {
  const { list, branchOptions, filters, setSearch, setBranch, setAccess, setPage } = useEmployeeAccessList();
  const rows = list.data?.results ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-72 max-w-full">
          <i className="ti ti-search pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--on-variant)]" />
          <input className="finput w-full !pl-9" type="search" value={filters.search} onChange={event => setSearch(event.target.value)} placeholder="Search name, email or ID" aria-label="Search employees" />
        </div>
        <select className="finput w-48" value={filters.branch} onChange={event => setBranch(event.target.value)} aria-label="Filter by branch">
          <option value="">All branches</option>
          {branchOptions.map(branch => <option key={branch.id} value={branch.branch_name}>{branch.branch_name}</option>)}
        </select>
        {list.data && <span className="ml-auto text-sm text-[var(--on-variant)]">{list.data.count} employee{list.data.count === 1 ? "" : "s"}</span>}
      </div>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by access">
        {ACCESS_OPTIONS.map(option => {
          const isActive = filters.access === option.value;
          return (
            <button
              key={option.value || "all"} type="button" aria-pressed={isActive} onClick={() => setAccess(option.value)}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors"
              style={isActive
                ? { background: "var(--primary)", borderColor: "var(--primary)", color: "#fff" }
                : { background: "var(--surface)", borderColor: "var(--outline-v)", color: "var(--on-variant)" }}
            >
              <i className={`ti ${option.icon}`} /> {option.label}
            </button>
          );
        })}
      </div>

      {list.error && <div className="alert alert-error" role="alert">{list.error}</div>}

      <div className="overflow-x-auto rounded-2xl border border-[var(--outline-v)]" style={{ background: "var(--surface)" }}>
        <table className="w-full min-w-[820px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-[var(--outline-v)] text-left text-[11px] font-bold uppercase tracking-[0.06em] text-[var(--on-variant)]" style={{ background: "var(--bg-low)" }}>
              <th className="px-4 py-3">Employee</th>
              <th className="px-3 py-3">Position</th>
              <th className="px-3 py-3">Company code</th>
              <th className="px-3 py-3">Permissions</th>
              <th className="px-3 py-3 text-right">Extra</th>
              <th className="px-3 py-3" />
            </tr>
          </thead>
          <tbody>
            {list.loading && <tr><td colSpan={6} className="px-4 py-8 text-center text-[var(--on-variant)]">Loading…</td></tr>}
            {!list.loading && rows.length === 0 && <tr><td colSpan={6} className="px-4 py-8 text-center text-[var(--on-variant)]">No employee matches those filters.</td></tr>}
            {rows.map(row => (
              <tr key={row.uuid} className="cursor-pointer border-b border-[var(--outline-v)] last:border-b-0 hover:bg-[var(--bg-low)]" onClick={() => onSelect(row)}>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-3">
                    <Avatar name={row.full_name} />
                    <div>
                      <div className="font-semibold text-[var(--on-bg)]">{row.full_name}</div>
                      <div className="text-xs text-[var(--on-variant)]">{row.employee_id}</div>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-2.5 text-[var(--on-variant)]">
                  {row.position || (row.is_superuser ? "—" : <Badge tone="var(--warn)"><i className="ti ti-alert-circle" /> No position</Badge>)}
                </td>
                <td className="px-3 py-2.5 text-[var(--on-variant)]">{row.branch || "—"}</td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <strong className="w-8 text-[var(--on-bg)]">{row.is_superuser ? "All" : row.total}</strong>
                    <ShareBar row={row} />
                    {row.is_superuser && <Badge tone="var(--primary)"><i className="ti ti-crown" /> Superuser</Badge>}
                  </div>
                </td>
                <td className="px-3 py-2.5 text-right">
                  {row.is_superuser ? <span className="text-[var(--on-variant)]">—</span> : row.extra > 0 ? <Badge tone="var(--primary)">+{row.extra}</Badge> : <span className="text-[var(--on-variant)]">0</span>}
                </td>
                <td className="px-3 py-2.5 text-right">
                  <button
                    type="button" className="inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-semibold"
                    style={{ borderColor: "var(--outline-v)", color: "var(--primary)", background: "var(--surface)" }}
                    onClick={event => { event.stopPropagation(); onSelect(row); }}
                  >
                    Manage access <i className="ti ti-arrow-right" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11.5px] text-[var(--on-variant)]">
        <span><span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: SEGMENT_COLORS.everyone, filter: "brightness(.85)" }} />From everyone (baseline)</span>
        <span><span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: SEGMENT_COLORS.position }} />From their position</span>
        <span><span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: SEGMENT_COLORS.extra }} />Given to them personally</span>
      </p>

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
