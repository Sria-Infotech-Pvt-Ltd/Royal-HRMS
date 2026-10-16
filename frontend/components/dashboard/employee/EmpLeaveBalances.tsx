"use client";

import { useState } from "react";
import { useLeaveBalances } from "@/hooks/useEmployeeDashboard";
import { getLeaveYear } from "@/lib/fiscalYear";
import { monthTotals, scheduleLabel, signed, typesWithBreakdown } from "@/lib/leaveBreakdown";
import type { LeaveBalance, LeaveStatement } from "@/types/employeeDashboard";
import AssessmentLockedNotice from "./AssessmentLockedNotice";

const LEAVE_TYPE_LABEL: Record<string, string> = {
  casual:    "Casual Leave",
  sick:      "Sick Leave",
  earned:    "Earned Leave",
  maternity: "Maternity Leave",
  paternity: "Paternity Leave",
  lwp:       "Leave Without Pay",
};

const LEAVE_TYPE_COLOR: Record<string, string> = {
  casual:    "var(--info)",
  sick:      "var(--warn)",
  earned:    "var(--success)",
  maternity: "var(--secondary)",
  paternity: "var(--primary)",
  lwp:       "var(--outline)",
};

// Month-by-month view of what was recorded for each leave type. These are
// recorded movements, not month-end balances — the yearly available balance
// (the cards above) stays the figure that leave applications use.
// Monthly-schedule leave types: the full statement (carried in, credit,
// used, pending, expired, closing), reconciled with the yearly balance.
function StatementTable({ stmt, cell }: { stmt: LeaveStatement; cell: React.CSSProperties }) {
  const show = (n: number) => (n ? n : "—");
  return (
    <div style={{ overflowX: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
      <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--bg-low)", color: "var(--on-variant)" }}>
            <th style={{ padding: "6px 8px", textAlign: "left" }}>Month</th>
            <th style={cell}>Carried in</th>
            <th style={cell}>Credit</th>
            <th style={cell}>Used</th>
            <th style={cell}>Pending</th>
            <th style={cell}>Expired</th>
            <th style={cell}>Available at month end</th>
          </tr>
        </thead>
        <tbody>
          {stmt.months.map(m => (
            <tr key={m.month} style={{ borderTop: "1px solid var(--border)" }}>
              <td style={{ padding: "6px 8px" }}>
                {m.label}
                {m.carry_off && !m.closed && m.credit_left > 0 && (
                  <div style={{ fontSize: 10.5, color: "var(--warn)" }}>{m.credit_left} usable this month only</div>
                )}
              </td>
              <td style={cell}>{show(m.carried_in)}</td>
              <td style={cell}>{show(m.credit)}</td>
              <td style={cell}>{show(m.used)}</td>
              <td style={cell}>{show(m.pending)}</td>
              <td style={{ ...cell, color: m.expired ? "var(--error)" : undefined }}>{show(m.expired)}</td>
              <td style={{ ...cell, fontWeight: 600 }}>{m.closing}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MonthlyBreakdown({ balances, year }: { balances: LeaveBalance[]; year: number }) {
  const types = typesWithBreakdown(balances);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState("");
  if (!types.length) return null;
  const current = types.find(t => t.leave_type === selected) ?? types[0];
  const months = current.monthly?.months ?? [];
  const totals = monthTotals(months);
  const notItemised = current.monthly?.used_not_itemised ?? 0;
  const label = (b: LeaveBalance) => b.leave_type_label || LEAVE_TYPE_LABEL[b.leave_type] || b.leave_type;
  const cell = { padding: "6px 8px", textAlign: "right" as const };

  return (
    <div style={{ borderTop: "1px solid var(--border)" }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        style={{
          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "10px 16px", background: "none", border: "none", cursor: "pointer",
          fontSize: 12.5, fontWeight: 600, color: "var(--on-bg)", textAlign: "left",
        }}
      >
        <span><i className="ti ti-calendar-stats" style={{ marginRight: 6 }} />Month-by-month — {year}</span>
        <i className={`ti ${open ? "ti-chevron-down" : "ti-chevron-right"}`} aria-hidden="true" style={{ color: "var(--on-variant)" }} />
      </button>

      {open && (
        <div style={{ padding: "0 16px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {types.map(t => (
              <button key={t.leave_type} type="button" onClick={() => setSelected(t.leave_type)}
                className={`btn btn-sm ${t.leave_type === current.leave_type ? "btn-filled" : "btn-ghost"}`}>
                {label(t)}
              </button>
            ))}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>{scheduleLabel(current)}</div>

          {current.statement ? (
            <>
              {current.statement.opening !== 0 && (
                <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>
                  Opening {current.statement.opening} day(s) (opening balance, carried forward and adjustments) never expire.
                </div>
              )}
              <StatementTable stmt={current.statement} cell={cell} />
            </>
          ) : (
          <div style={{ overflowX: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
            <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "var(--bg-low)", color: "var(--on-variant)" }}>
                  <th style={{ padding: "6px 8px", textAlign: "left" }}>Month</th>
                  <th style={cell}>Monthly credit</th>
                  <th style={cell}>Other adjustments</th>
                  <th style={cell}>Leave used</th>
                </tr>
              </thead>
              <tbody>
                {months.map(m => (
                  <tr key={m.month} style={{ borderTop: "1px solid var(--border)" }}>
                    <td style={{ padding: "6px 8px" }}>{m.label}</td>
                    <td style={cell}>{m.monthly_credit || "—"}</td>
                    <td style={cell}>{m.other_adjustments ? signed(m.other_adjustments) : "—"}</td>
                    <td style={cell}>{m.used || "—"}</td>
                  </tr>
                ))}
                <tr style={{ borderTop: "1px solid var(--border)", fontWeight: 700 }}>
                  <td style={{ padding: "6px 8px" }}>Total recorded</td>
                  <td style={cell}>{totals.monthly_credit}</td>
                  <td style={cell}>{signed(totals.other_adjustments)}</td>
                  <td style={cell}>{totals.used}</td>
                </tr>
              </tbody>
            </table>
          </div>
          )}
          {notItemised > 0 && (
            <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>
              {notItemised} day(s) used aren&apos;t linked to a specific month (for example, leave included in an imported opening balance).
            </div>
          )}

          <div style={{ padding: "8px 12px", borderRadius: 8, background: "var(--bg-low)", fontSize: 12.5 }}>
            <strong>Yearly balance {year}:</strong> total {current.total_days}, used {current.used_days},{" "}
            <strong>available {current.remaining}</strong>.
            <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2 }}>
              {current.statement
                ? (current.statement.reconciled
                    ? "The month-end figures add up to this yearly balance (after pending leave)."
                    : "Month-end processing for a past month is still due; the yearly figure is current.")
                : "The months show what was recorded each month. Month-end balances aren't calculated for this leave type, so your available leave is the yearly figure."}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function EmpLeaveBalances() {
  const year = getLeaveYear();
  const { data, loading, status } = useLeaveBalances(year);

  const balances = data?.balances ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-beach" /> Leave Balances — {year}</div>
        <a href="/dashboard/leave" className="btn btn-ghost btn-sm">Apply Leave</a>
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : status === 403 ? (
        <AssessmentLockedNotice />
      ) : balances.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          No leave balances found. Contact HR to credit your leave.
        </div>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>
            {balances.map(b => {
              const pct   = b.total_days > 0 ? Math.min(100, (b.remaining / b.total_days) * 100) : 0;
              const color = LEAVE_TYPE_COLOR[b.leave_type] ?? "var(--primary)";
              const label = b.leave_type_label || LEAVE_TYPE_LABEL[b.leave_type] || b.leave_type;
              return (
                <div key={b.leave_type} style={{ padding: "12px 16px", borderRight: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, fontWeight: 600, color: "var(--on-bg)" }}>{label}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 20, fontWeight: 800, color: "var(--on-bg)", lineHeight: 1 }}>{b.remaining}</span>
                    <span style={{ fontSize: 11, color: "var(--on-variant)", alignSelf: "flex-end" }}>of {b.total_days} days</span>
                  </div>
                  <div style={{ height: 5, borderRadius: 3, background: "var(--bg-high)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 3, transition: "width 0.4s ease" }} />
                  </div>
                  {b.used_days > 0 && (
                    <div style={{ fontSize: 10, color: "var(--on-variant)", marginTop: 4 }}>{b.used_days} used{b.carried_forward > 0 ? ` · ${b.carried_forward} carried forward` : ""}</div>
                  )}
                </div>
              );
            })}
          </div>
          {(data?.lop_days ?? 0) > 0 && (
            <div style={{ padding: "8px 16px", borderTop: "1px solid var(--border)", fontSize: 12, color: "var(--error)", display: "flex", alignItems: "center", gap: 6 }}>
              <i className="ti ti-alert-circle" style={{ fontSize: 13 }} />
              {data?.lop_days} LOP day{(data?.lop_days ?? 0) !== 1 ? "s" : ""} this year
            </div>
          )}
          <MonthlyBreakdown balances={balances} year={year} />
        </>
      )}
    </div>
  );
}
