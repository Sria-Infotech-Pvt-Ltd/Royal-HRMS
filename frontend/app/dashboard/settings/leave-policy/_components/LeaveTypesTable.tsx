"use client";

// The leave types as a table: a coloured icon and name, the annual days as a bar, coloured accrual and carry-forward pills, a real on/off
// switch for the status, the policy note, and edit and delete buttons. A search box and status buttons narrow the list.

import { useState } from "react";
import { BUILTIN_TYPES, filterLeaveTypes, leaveTypeColour, leaveTypeIcon, tint, type LeavePolicy, type StatusFilter } from "./leaveTypeView";

interface Props {
  list: LeavePolicy[];
  loading: boolean;
  error: string | null;
  rowError: string | null;
  busyType: string | null;
  onCreate: () => void;
  onEdit: (policy: LeavePolicy) => void;
  onToggle: (policy: LeavePolicy) => void;
  onDelete: (policy: LeavePolicy) => void;
}

const SHIMMER = { background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite" } as const;
const ICON_BUTTON = { width: 32, height: 32, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 9 } as const;

function Pill({ colour, children }: { colour: string; children: React.ReactNode }) {
  return <span style={{ display: "inline-block", fontSize: 12, fontWeight: 700, padding: "3px 11px", borderRadius: 999, whiteSpace: "nowrap", background: tint(colour, 0.14), color: colour }}>{children}</span>;
}

export default function LeaveTypesTable({ list, loading, error, rowError, busyType, onCreate, onEdit, onToggle, onDelete }: Props) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const visible = filterLeaveTypes(list, search, status);
  const mostDays = Math.max(1, ...list.map(policy => Number(policy.annual_days)));

  return (
    <section aria-label="Leave types" className="card" style={{ padding: 0, overflow: "hidden" }}>
      <header style={{ padding: "14px 20px", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", borderBottom: "1px solid var(--outline-v)" }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "var(--on-bg)", display: "flex", alignItems: "center", gap: 8, flex: "1 1 160px" }}>
          <i className="ti ti-beach" aria-hidden="true" style={{ color: "var(--brand)" }} /> Leave Types
          {!loading && <span style={{ fontSize: 12, fontWeight: 700, padding: "2px 10px", borderRadius: 999, background: tint("var(--brand)", 0.12), color: "var(--brand)" }}>{list.length}</span>}
        </h3>
        <div style={{ position: "relative", flex: "0 1 260px" }}>
          <i className="ti ti-search" aria-hidden="true" style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", color: "var(--on-variant)" }} />
          <input className="field-input" type="search" aria-label="Search leave types" placeholder="Search leave types…" value={search} onChange={event => setSearch(event.target.value)} style={{ paddingLeft: 32, width: "100%" }} />
        </div>
        <button className="btn btn-filled btn-sm" onClick={onCreate}><i className="ti ti-plus" /> Add Leave Type</button>
      </header>

      <div role="group" aria-label="Show" style={{ display: "flex", gap: 6, padding: "10px 20px", background: "var(--bg-low)", borderBottom: "1px solid var(--outline-v)" }}>
        {(["all", "active", "inactive"] as const).map(option => {
          const selected = status === option;
          return (
            <button key={option} type="button" aria-pressed={selected} onClick={() => setStatus(option)}
              style={{ padding: "5px 13px", borderRadius: 999, fontSize: 12.5, fontWeight: 700, cursor: "pointer", textTransform: "capitalize", border: `1.5px solid ${selected ? "var(--brand)" : "var(--outline-v)"}`, background: selected ? tint("var(--brand)", 0.12) : "var(--surface)", color: selected ? "var(--brand)" : "var(--on-variant)" }}>{option}</button>
          );
        })}
      </div>

      {error && <div role="alert" style={{ margin: 16, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 10, color: "var(--error)", fontSize: 13 }}>{error}</div>}
      {rowError && <div role="alert" style={{ margin: 16, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 10, color: "var(--error)", fontSize: 13 }}>{rowError}</div>}

      {!error && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Type</th><th>Annual Days</th><th style={{ textAlign: "center" }}>Accrual</th><th style={{ textAlign: "center" }}>Carry Forward</th><th style={{ textAlign: "center" }}>Active</th><th>Policy Note</th><th style={{ textAlign: "center" }}>Actions</th></tr>
            </thead>
            <tbody>
              {loading && [0, 1, 2, 3].map(row => (
                <tr key={row} aria-label="Loading">{Array.from({ length: 7 }, (_, cell) => <td key={cell}><div aria-hidden="true" style={{ ...SHIMMER, height: 14, borderRadius: 6 }} /></td>)}</tr>
              ))}
              {!loading && visible.length === 0 && (
                <tr><td colSpan={7} style={{ padding: "36px 12px", textAlign: "center", color: "var(--on-variant)" }}>
                  <i className="ti ti-beach-off" aria-hidden="true" style={{ fontSize: 34, color: "var(--outline)" }} />
                  <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 6 }}>{list.length === 0 ? "No leave types yet." : "No leave types match."}</div>
                  <div style={{ fontSize: 12.5, marginTop: 2 }}>{list.length === 0 ? "Add the first one to get started." : "Try another word or show all."}</div>
                </td></tr>
              )}
              {!loading && visible.map(policy => {
                const colour = leaveTypeColour(policy.leave_type);
                const days = Number(policy.annual_days);
                const builtIn = BUILTIN_TYPES.has(policy.leave_type);
                const busy = busyType === policy.leave_type;
                return (
                  <tr key={policy.leave_type} style={{ opacity: policy.is_active ? 1 : 0.62 }}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span aria-hidden="true" style={{ width: 34, height: 34, borderRadius: 10, flexShrink: 0, display: "grid", placeItems: "center", fontSize: 18, background: tint(colour, 0.14), color: colour }}><i className={`ti ${leaveTypeIcon(policy.leave_type)}`} /></span>
                        <div>
                          <div style={{ fontWeight: 700, fontSize: 13.5, color: "var(--on-bg)" }}>{policy.leave_type_display}</div>
                          <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{builtIn ? "Built-in" : "Custom"}</div>
                        </div>
                      </div>
                    </td>
                    <td style={{ minWidth: 130 }}>
                      <div style={{ fontWeight: 800, fontSize: 15, color: colour, fontVariantNumeric: "tabular-nums" }}>{days} <span style={{ fontSize: 11, fontWeight: 600, color: "var(--on-variant)" }}>days</span></div>
                      <div aria-hidden="true" style={{ height: 5, borderRadius: 999, background: tint(colour, 0.14), marginTop: 5 }}><div style={{ height: "100%", width: `${Math.round((days / mostDays) * 100)}%`, borderRadius: 999, background: colour }} /></div>
                    </td>
                    <td style={{ textAlign: "center" }}><Pill colour={policy.accrual_frequency === "monthly" ? "#2563EB" : "#64748B"}>{policy.accrual_frequency === "monthly" ? "Monthly" : "Annual"}</Pill></td>
                    <td style={{ textAlign: "center" }}>
                      {policy.can_carry_forward ? <Pill colour="#16A34A">Yes · up to {policy.max_carry_forward_days}d</Pill> : <Pill colour="#64748B">No</Pill>}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <button
                        type="button" role="switch" aria-checked={policy.is_active} aria-label={`${policy.leave_type_display} active`} title={policy.is_active ? "Deactivate" : "Activate"}
                        disabled={busy} onClick={() => onToggle(policy)}
                        style={{ width: 40, height: 22, borderRadius: 999, border: 0, padding: 2, cursor: busy ? "wait" : "pointer", background: policy.is_active ? "#16A34A" : "#CBD5E1", transition: "background .18s ease", display: "inline-flex", alignItems: "center", justifyContent: policy.is_active ? "flex-end" : "flex-start" }}
                      ><span aria-hidden="true" style={{ width: 18, height: 18, borderRadius: "50%", background: "#fff", boxShadow: "0 1px 3px rgba(0,0,0,.3)" }} /></button>
                    </td>
                    <td style={{ fontSize: 12.5, color: "var(--on-variant)", maxWidth: 280 }}>{policy.policy_note || <span style={{ color: "var(--outline)" }}>—</span>}</td>
                    <td style={{ textAlign: "center" }}>
                      <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
                        <button className="btn btn-ghost" style={{ ...ICON_BUTTON, color: "var(--brand)" }} onClick={() => onEdit(policy)} title="Edit" aria-label={`Edit ${policy.leave_type_display}`}><i className="ti ti-edit" style={{ fontSize: 15 }} /></button>
                        <button className="btn btn-ghost" style={{ ...ICON_BUTTON, color: builtIn ? "var(--outline)" : "#DC2626", cursor: builtIn ? "not-allowed" : "pointer" }} onClick={() => onDelete(policy)} disabled={busy || builtIn}
                          title={builtIn ? "Built-in leave types cannot be deleted" : "Delete"} aria-label={`Delete ${policy.leave_type_display}`}><i className="ti ti-trash" style={{ fontSize: 15 }} /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
