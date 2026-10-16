"use client";

// Month-by-month view of a Monthly-schedule leave type, rendered from the
// backend statement (credited, used, pending, expired, carried in, balance).
// Responsive month cards rather than a wide table. Figures are displayed as
// returned — nothing is calculated here.

import { useState } from "react";
import { monthLines, scheduleChip, statementNotes } from "@/lib/leaveStatement";
import type { LeaveStatement, LeaveStatementMonth } from "@/types/employeeDashboard";

export default function MonthlyLeaveStatement({ label, year, stmt, total, used, available, defaultOpen = true }: {
  label: string; year: number; stmt: LeaveStatement;
  total: number; used: number; available: number; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const notes = statementNotes(stmt, year);

  return (
    <div className="card">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        className="card-header"
        style={{ width: "100%", background: "none", border: "none", cursor: "pointer", textAlign: "left", font: "inherit",
                 borderBottom: open ? "1px solid var(--outline-v)" : "none", flexWrap: "wrap", gap: 8 }}
      >
        <span className="card-title"><i className="ti ti-calendar-stats" /> {label} — {year}</span>
        <span style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12, color: "var(--on-variant)" }}>
          {scheduleChip(stmt)}
          <i className={`ti ${open ? "ti-chevron-down" : "ti-chevron-right"}`} aria-hidden="true" style={{ fontSize: 16 }} />
        </span>
      </button>

      {open && (
        <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
          {notes.map(n => (
            <div key={n} style={{ fontSize: 12, color: "var(--on-variant)" }}><i className="ti ti-info-circle" /> {n}</div>
          ))}

          {stmt.months.length === 0 ? (
            <div style={{ fontSize: 13, color: "var(--on-variant)" }}>No months to show for {year} yet.</div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
              {stmt.months.map(m => (
                <div key={m.month} style={{ border: "1px solid var(--outline-v)", borderRadius: 8, padding: "10px 12px", background: "#fff" }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--on-bg)", marginBottom: 6 }}>
                    {m.label}
                    {!m.closed && <span style={{ fontSize: 10.5, fontWeight: 500, color: "var(--primary)", marginLeft: 6 }}>open</span>}
                  </div>
                  {monthLines(m).map(line => (
                    <div key={line.key} style={{
                      display: "flex", justifyContent: "space-between", fontSize: 12, lineHeight: 1.7,
                      color: line.tone === "error" ? "var(--error)" : "var(--on-variant)",
                      fontWeight: line.tone === "strong" ? 700 : 400,
                      borderTop: line.key === "closing" ? "1px solid var(--outline-v)" : undefined,
                      marginTop: line.key === "closing" ? 4 : 0, paddingTop: line.key === "closing" ? 4 : 0,
                    }}>
                      <span>{line.label}</span>
                      <span style={{ color: line.tone === "strong" ? "var(--on-bg)" : undefined }}>{line.value}</span>
                    </div>
                  ))}
                  {m.carry_off && !m.closed && m.credit_left > 0 && (
                    <div style={{ fontSize: 10.5, color: "var(--warn)", marginTop: 4 }}>{m.credit_left} usable this month only</div>
                  )}
                </div>
              ))}
            </div>
          )}

          <div style={{ padding: "8px 12px", borderRadius: 8, background: "var(--bg-low)", fontSize: 12.5 }}>
            <strong>Yearly balance {year}:</strong> credited {stmt.total_credited ?? total}
            {stmt.total_expired ? `, expired ${stmt.total_expired}` : ""}, total {total}, used {used},{" "}
            <strong>available {available}</strong>
            {stmt.total_pending ? ` (${stmt.total_pending} pending)` : ""}.
          </div>
        </div>
      )}
    </div>
  );
}

/** Monthly view → Manage Leave Credits: one row per Monthly leave type for the selected month,
 *  read from each type's backend statement (no frontend calculation). */
export function MonthlyCreditsTable({ rows, year, month, monthOptions, onMonth }: {
  rows: { leave_type: string; label: string; month: LeaveStatementMonth | null; hasStatement: boolean }[];
  year: number; month: number; monthOptions: { value: number; label: string }[];
  onMonth: (m: number) => void;
}) {
  const num = (v: number | undefined) => (v ? v : "—");
  return (
    <div className="card">
      <div className="card-header" style={{ flexWrap: "wrap", gap: 10 }}>
        <div className="card-title"><i className="ti ti-adjustments-horizontal" /> Monthly Leave Credits</div>
        <select className="field-input" style={{ width: "auto", padding: "6px 10px" }} aria-label="Month"
          value={month} onChange={e => onMonth(Number(e.target.value))}>
          {monthOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Leave Type</th>
              <th style={{ textAlign: "right" }}>Carried in</th>
              <th style={{ textAlign: "right" }}>Credited</th>
              <th style={{ textAlign: "right" }}>Used</th>
              <th style={{ textAlign: "right" }}>Pending</th>
              <th style={{ textAlign: "right" }}>Expired</th>
              <th style={{ textAlign: "right" }}>Balance</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.leave_type}>
                <td style={{ fontWeight: 600 }}>{r.label}</td>
                {!r.hasStatement ? (
                  <td colSpan={6} style={{ color: "var(--on-variant)" }}>Monthly breakdown isn&apos;t available to you for this employee.</td>
                ) : !r.month ? (
                  <td colSpan={6} style={{ color: "var(--on-variant)" }}>Nothing recorded for this month in {year}.</td>
                ) : (
                  <>
                    <td style={{ textAlign: "right" }}>{num(r.month.carried_in)}</td>
                    <td style={{ textAlign: "right" }}>{num(r.month.credit)}</td>
                    <td style={{ textAlign: "right" }}>{num(r.month.used)}</td>
                    <td style={{ textAlign: "right" }}>{num(r.month.pending)}</td>
                    <td style={{ textAlign: "right", color: r.month.expired ? "var(--error)" : undefined }}>
                      {r.month.carry_off ? num(r.month.expired) : "n/a"}
                    </td>
                    <td style={{ textAlign: "right", fontWeight: 700 }}>{r.month.closing}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
