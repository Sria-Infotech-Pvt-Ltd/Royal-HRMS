"use client";

import { useState } from "react";
import { EMP_DATA, grossEarnings, totalDeductions, totalReimb, netSalary, fmt } from "./payrollData";

interface Props { onNext: () => void; onBack: () => void; }

export default function CalculationStep({ onNext, onBack }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [calculated, setCalculated] = useState(false);

  const toggle = (id: string) => setExpanded(p => p === id ? null : id);

  const totalGross = EMP_DATA.reduce((s, e) => s + grossEarnings(e), 0);
  const totalDed   = EMP_DATA.reduce((s, e) => s + totalDeductions(e), 0);
  const totalReim  = EMP_DATA.reduce((s, e) => s + totalReimb(e), 0);
  const totalNet   = EMP_DATA.reduce((s, e) => s + netSalary(e), 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Summary bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        {[
          { label: "Total Gross",       value: totalGross, color: "var(--primary)", icon: "ti-cash"          },
          { label: "Total Deductions",  value: totalDed,   color: "var(--error)",   icon: "ti-minus-vertical"},
          { label: "Total Reimb.",      value: totalReim,  color: "var(--info)",    icon: "ti-receipt"       },
          { label: "Total Net Payable", value: totalNet,   color: "var(--success)", icon: "ti-credit-card"   },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div className="stat-label">{s.label}</div>
            <div className="stat-value" style={{ fontSize: 20, color: s.color }}>{fmt(s.value)}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-calculator" /> Payroll Calculation — June 2026</div>
          <div style={{ display: "flex", gap: 8 }}>
            {!calculated
              ? <button className="btn btn-filled btn-sm" onClick={() => setCalculated(true)}><i className="ti ti-calculator" /> Calculate</button>
              : <button className="btn btn-outline btn-sm" onClick={() => setCalculated(true)}><i className="ti ti-refresh" /> Recalculate</button>}
            <span className="badge badge-info">Step 7 of 11</span>
          </div>
        </div>

        {!calculated ? (
          <div className="empty-state" style={{ padding: "40px 20px" }}>
            <i className="ti ti-calculator" style={{ fontSize: 40, color: "var(--outline)" }} />
            <h3 style={{ marginTop: 12 }}>Click Calculate to compute salaries</h3>
            <p style={{ color: "var(--on-variant)" }}>All earnings, deductions and reimbursements have been reviewed.</p>
            <button className="btn btn-filled" style={{ marginTop: 16 }} onClick={() => setCalculated(true)}>
              <i className="ti ti-calculator" /> Calculate All Salaries
            </button>
          </div>
        ) : (
          <div>
            {EMP_DATA.map(e => {
              const gross = grossEarnings(e);
              const ded   = totalDeductions(e);
              const reimb = totalReimb(e);
              const net   = netSalary(e);
              const isOpen = expanded === e.id;

              return (
                <div key={e.id} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                  <div
                    style={{ display: "flex", alignItems: "center", padding: "14px 20px", cursor: "pointer", gap: 12 }}
                    onClick={() => toggle(e.id)}
                  >
                    <div style={{ width: 34, height: 34, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700 }}>{e.avatar}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600 }}>{e.name}</div>
                      <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{e.designation} · {e.dept}</div>
                    </div>
                    <div style={{ textAlign: "right", marginRight: 16 }}>
                      <div style={{ fontSize: 12, color: "var(--on-variant)" }}>Gross</div>
                      <div style={{ fontWeight: 600 }}>{fmt(gross)}</div>
                    </div>
                    <div style={{ textAlign: "right", marginRight: 16 }}>
                      <div style={{ fontSize: 12, color: "var(--on-variant)" }}>Deductions</div>
                      <div style={{ fontWeight: 600, color: "var(--error)" }}>{fmt(ded)}</div>
                    </div>
                    <div style={{ textAlign: "right", marginRight: 20 }}>
                      <div style={{ fontSize: 12, color: "var(--on-variant)" }}>Net Salary</div>
                      <div style={{ fontWeight: 700, color: "var(--success)", fontSize: 16 }}>{fmt(net)}</div>
                    </div>
                    <i className={`ti ${isOpen ? "ti-chevron-up" : "ti-chevron-down"}`} style={{ color: "var(--outline)" }} />
                  </div>

                  {isOpen && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 0, background: "var(--bg-low)", borderTop: "1px solid var(--outline-v)", padding: "0 20px 16px" }}>
                      {/* Earnings */}
                      <div style={{ padding: "16px 16px 0 0" }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 10 }}>Earnings</div>
                        {[["Basic Salary", e.basic],["HRA", e.hra],["DA", e.da],["Special Allowance", e.special],["Bonus", e.bonus],["Overtime", e.ot]].map(([k, v]) => (
                          <div key={k as string} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
                            <span style={{ color: "var(--on-variant)" }}>+ {k}</span>
                            <span>{fmt(v as number)}</span>
                          </div>
                        ))}
                        <div style={{ borderTop: "1.5px solid var(--outline-v)", paddingTop: 6, marginTop: 6, display: "flex", justifyContent: "space-between", fontWeight: 700 }}>
                          <span>= Gross Salary</span><span style={{ color: "var(--primary)" }}>{fmt(gross)}</span>
                        </div>
                      </div>

                      {/* Deductions */}
                      <div style={{ padding: "16px", borderLeft: "1px solid var(--outline-v)", borderRight: "1px solid var(--outline-v)" }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 10 }}>Deductions</div>
                        {[["PF", e.pf],["ESI", e.esi],["PT", e.pt],["TDS", e.tds],["LOP", e.lop],["Loan EMI", e.loan_emi],["Advance", e.advance]].map(([k, v]) => (v as number) > 0 && (
                          <div key={k as string} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
                            <span style={{ color: "var(--on-variant)" }}>- {k}</span>
                            <span style={{ color: "var(--error)" }}>{fmt(v as number)}</span>
                          </div>
                        ))}
                        <div style={{ borderTop: "1.5px solid var(--outline-v)", paddingTop: 6, marginTop: 6, display: "flex", justifyContent: "space-between", fontWeight: 700 }}>
                          <span>= Total Deductions</span><span style={{ color: "var(--error)" }}>{fmt(ded)}</span>
                        </div>
                      </div>

                      {/* Net */}
                      <div style={{ padding: "16px 0 0 16px" }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 10 }}>Reimbursements</div>
                        {[["Travel", e.travel],["Fuel", e.fuel],["Medical", e.medical],["Internet", e.internet],["Food", e.food]].map(([k, v]) => (
                          <div key={k as string} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
                            <span style={{ color: "var(--on-variant)" }}>+ {k}</span>
                            <span>{(v as number) > 0 ? fmt(v as number) : "—"}</span>
                          </div>
                        ))}
                        <div style={{ borderTop: "1.5px solid var(--outline-v)", paddingTop: 10, marginTop: 10, background: "rgba(27,138,107,0.06)", borderRadius: "var(--radius)", padding: "10px 12px" }}>
                          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 4 }}>Net Salary Payable</div>
                          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--success)" }}>{fmt(net)}</div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
          <button className="btn btn-filled" onClick={onNext} disabled={!calculated}>Continue <i className="ti ti-arrow-right" /></button>
        </div>
      </div>
    </div>
  );
}
