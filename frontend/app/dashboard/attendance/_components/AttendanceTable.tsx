"use client";

// The Team Day View table: five columns instead of nine. Clock in and out share one cell, hours and overtime share one, and the
// whole row opens the day's detail. Employee, Time and Status can be sorted.

import type { AttendanceRow } from "@/types/attendance";
import { PALETTE, statusColour, tint } from "./attendancePalette";
import { isBlank, nextSort, summariseTimes, type SortKey, type SortState } from "./attendanceView";

function StatusPill({ statusKey, label }: { statusKey: string; label: string }) {
  const colour = statusColour(statusKey);
  return <span style={{ display: "inline-block", fontSize: 12, fontWeight: 700, padding: "3px 11px", borderRadius: 999, background: tint(colour, 0.14), color: colour }}>{label}</span>;
}
const MONO: React.CSSProperties = { fontFamily: "Menlo, Consolas, monospace", fontSize: 12.5 };

interface Props {
  rows: AttendanceRow[];
  loading: boolean;
  sort: SortState;
  onSortChange: (sort: SortState) => void;
  onOpen: (row: AttendanceRow) => void;
}

function SortHeader({ label, sortKey, sort, onSortChange }: { label: string; sortKey: SortKey; sort: SortState; onSortChange: (sort: SortState) => void }) {
  const active = sort.by === sortKey;
  return (
    <th aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}>
      <button
        type="button" onClick={() => onSortChange(nextSort(sort, sortKey))} aria-label={`Sort by ${label}`}
        style={{ display: "inline-flex", alignItems: "center", gap: 4, background: "none", border: 0, padding: 0, cursor: "pointer", font: "inherit", color: "inherit", textTransform: "inherit", letterSpacing: "inherit" }}
      >
        {label}
        <i className={`ti ${active ? (sort.dir === "asc" ? "ti-arrow-up" : "ti-arrow-down") : "ti-arrows-sort"}`} aria-hidden="true" style={{ fontSize: 12, opacity: active ? 1 : 0.4 }} />
      </button>
    </th>
  );
}

function TimeCell({ row }: { row: AttendanceRow }) {
  const times = summariseTimes(row.clock_in, row.clock_out);
  if (times.kind === "none") return <span style={{ color: "var(--outline)", fontSize: 12.5 }}>No punch</span>;
  return (
    <span style={MONO}>
      <span style={{ color: row.is_late ? PALETTE.late : "var(--on-bg)", fontWeight: row.is_late ? 700 : 400 }} title={row.is_late ? "Arrived late" : undefined}>{times.clockIn}</span>
      <span aria-hidden="true" style={{ color: "var(--outline)", margin: "0 6px" }}>→</span>
      <span style={{ color: times.clockOut === "—" ? "var(--outline)" : "var(--on-bg)" }}>{times.clockOut === "—" ? "still in" : times.clockOut}</span>
    </span>
  );
}

export default function AttendanceTable({ rows, loading, sort, onSortChange, onOpen }: Props) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <SortHeader label="Employee" sortKey="name" sort={sort} onSortChange={onSortChange} />
            <th>Department</th>
            <SortHeader label="Time" sortKey="clock_in" sort={sort} onSortChange={onSortChange} />
            <th>Hours</th>
            <SortHeader label="Status" sortKey="status" sort={sort} onSortChange={onSortChange} />
            <th aria-label="Open" />
          </tr>
        </thead>
        <tbody>
          {loading && <tr><td colSpan={6} style={{ textAlign: "center", padding: 28, color: "var(--on-variant)" }}>Loading…</td></tr>}
          {!loading && rows.length === 0 && <tr><td colSpan={6} style={{ textAlign: "center", padding: 28, color: "var(--on-variant)" }}>No attendance records for this filter.</td></tr>}
          {rows.map((row, index) => (
            <tr
              key={`${row.record_id ?? row.employee_id ?? "row"}-${index}`} tabIndex={0} aria-label={`Open ${row.name}`} style={{ cursor: "pointer" }}
              onClick={() => onOpen(row)} onKeyDown={event => { if (event.key === "Enter") onOpen(row); }}
            >
              <td>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div aria-hidden="true" style={{ width: 34, height: 34, borderRadius: "50%", background: "rgba(124,58,237,0.1)", color: "var(--primary)", fontSize: 11, fontWeight: 700, display: "grid", placeItems: "center", flexShrink: 0 }}>{row.initials}</div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13.5, color: "var(--on-bg)" }}>{row.name}</div>
                    <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>{row.employee_id}</div>
                  </div>
                </div>
              </td>
              <td>
                <div style={{ fontSize: 13 }}>{row.department}</div>
                <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>{row.branch}</div>
              </td>
              <td><TimeCell row={row} /></td>
              <td>
                {isBlank(row.total_hours) ? <span style={{ color: "var(--outline)" }}>—</span> : (
                  <span style={MONO}>
                    {row.total_hours}
                    {!isBlank(row.ot) && <span title="Overtime" style={{ marginLeft: 8, fontSize: 11, fontWeight: 700, padding: "1px 7px", borderRadius: 999, background: tint(PALETTE.present, 0.14), color: PALETTE.present }}>+{row.ot} OT</span>}
                  </span>
                )}
              </td>
              <td><StatusPill statusKey={row.status_key} label={row.status} /></td>
              <td style={{ textAlign: "right", color: "var(--outline)" }}><i className="ti ti-chevron-right" aria-hidden="true" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
