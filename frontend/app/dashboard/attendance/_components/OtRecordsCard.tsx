"use client";

// The OT records: a header with the total and the branch filter, then a table with coloured type and status pills, a shimmering
// placeholder while loading, a friendly empty state, and paging.

import type { ReactNode } from "react";
import type { OvertimeRow, PaginatedOvertime } from "@/types/attendance";
import { PALETTE, tint } from "./attendancePalette";
import { otStatusColour, otTypeColour } from "./otEntry";

interface Props {
  rows: OvertimeRow[];
  data: PaginatedOvertime | null;
  loading: boolean;
  error: string | null;
  page: number;
  onPage: (page: number) => void;
  /** The branch filter (a select) shown in the header. */
  filter: ReactNode;
}

const SHIMMER: React.CSSProperties = { background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite" };
const MONO: React.CSSProperties = { fontFamily: "Menlo, Consolas, monospace", fontSize: 12.5 };

function Pill({ colour, children }: { colour: string; children: ReactNode }) {
  return <span style={{ display: "inline-block", fontSize: 12, fontWeight: 700, padding: "3px 11px", borderRadius: 999, background: tint(colour, 0.14), color: colour }}>{children}</span>;
}

export default function OtRecordsCard({ rows, data, loading, error, page, onPage, filter }: Props) {
  return (
    <section aria-label="OT records" className="card" style={{ padding: 0, overflow: "hidden" }}>
      <header style={{ padding: "14px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, borderBottom: "1px solid var(--outline-v)" }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "var(--on-bg)", display: "flex", alignItems: "center", gap: 8 }}>
          <i className="ti ti-list-details" aria-hidden="true" style={{ color: PALETTE.brand }} /> OT Records
          {data && <span style={{ fontSize: 12, fontWeight: 700, padding: "2px 10px", borderRadius: 999, background: tint(PALETTE.brand, 0.12), color: PALETTE.brand }}>{data.count}</span>}
        </h3>
        {filter}
      </header>
      {error && <div className="alert alert-error" style={{ margin: 16 }}><i className="ti ti-alert-circle" /> {error}</div>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Employee</th><th>Date</th><th>OT Hours</th><th>Type</th><th>OT Amount</th><th>Approved By</th><th>Status</th></tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 3 }, (_, index) => (
              <tr key={`loading-${index}`} aria-label="Loading">{Array.from({ length: 7 }, (__, cell) => <td key={cell}><div aria-hidden="true" style={{ ...SHIMMER, height: 14, borderRadius: 6 }} /></td>)}</tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={7} style={{ padding: "34px 12px", textAlign: "center", color: "var(--on-variant)" }}>
                <i className="ti ti-clock-off" aria-hidden="true" style={{ fontSize: 32, color: "var(--outline)" }} />
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 6 }}>No overtime entries found.</div>
                <div style={{ fontSize: 12.5, marginTop: 2 }}>Entries you add above will appear here.</div>
              </td></tr>
            )}
            {rows.map(row => (
              <tr key={row.id}>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span aria-hidden="true" style={{ width: 32, height: 32, borderRadius: "50%", flexShrink: 0, display: "grid", placeItems: "center", fontSize: 11, fontWeight: 800, color: "#fff", background: `linear-gradient(135deg, ${PALETTE.brand}, #A78BFA)` }}>{row.initials}</span>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 13, color: "var(--on-bg)" }}>{row.name}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{row.employee_id}</div>
                    </div>
                  </div>
                </td>
                <td>{row.date}</td>
                <td style={{ ...MONO, fontWeight: 700 }}>{row.ot_hours}</td>
                <td><Pill colour={otTypeColour(row.ot_type)}>{row.ot_type}</Pill></td>
                <td style={{ ...MONO, fontWeight: 700 }}>{row.ot_amount}</td>
                <td>{row.approved_by}</td>
                <td><Pill colour={otStatusColour(row.status)}>{row.status}</Pill></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && data.total_pages > 1 && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {data.page} of {data.total_pages}</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onPage(Math.max(page - 1, 1))}><i className="ti ti-chevron-left" /> Prev</button>
            <button className="btn btn-ghost btn-sm" disabled={page >= data.total_pages} onClick={() => onPage(Math.min(page + 1, data.total_pages))}>Next <i className="ti ti-chevron-right" /></button>
          </div>
        </div>
      )}
    </section>
  );
}
