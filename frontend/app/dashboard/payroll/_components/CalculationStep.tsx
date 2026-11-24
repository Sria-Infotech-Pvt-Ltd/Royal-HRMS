"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useT } from "@/hooks/useI18n";
import { API } from "@/lib/api/endpoints";
import type { EmployeePayslip } from "@/types/payroll";

interface Props { cycleId: string; onNext: () => void; onBack: () => void; }
interface PagedResponse<T> { results: T[]; count: number; }

const fmt = (n: number | string) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

export default function CalculationStep({ cycleId, onNext, onBack }: Props) {
  const t = useT();
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data: payslipPage, loading, refetch } =
    useFetch<PagedResponse<EmployeePayslip>>(API.payroll.cyclePayslips(cycleId));

  const payslips = payslipPage?.results ?? [];

  const totalGross = payslips.reduce((s, p) => s + Number(p.gross_earnings), 0);
  const totalDed   = payslips.reduce((s, p) => s + Number(p.total_deductions), 0);
  const totalReim  = payslips.reduce((s, p) => s + Number(p.bonus ?? 0) + Number(p.reimbursements ?? 0), 0);
  const totalNet   = payslips.reduce((s, p) => s + Number(p.net_pay), 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Summary bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        {[
          { label: t("Total Gross"),       value: totalGross, color: "var(--primary)", icon: "ti-cash"           },
          { label: t("Total Deductions"),  value: totalDed,   color: "var(--error)",   icon: "ti-minus-vertical" },
          { label: t("Total Reimb./Bonus"),value: totalReim,  color: "var(--info)",    icon: "ti-receipt"        },
          { label: t("Net Payable"),       value: totalNet,   color: "var(--success)", icon: "ti-credit-card"    },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div className="stat-label">{s.label}</div>
            <div className="stat-value" style={{ fontSize: 20, color: s.color }}>
              {loading ? "—" : fmt(s.value)}
            </div>
            {!loading && <div className="stat-sub">{t("{count} employees", { count: payslips.length })}</div>}
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-calculator" /> {t("Final Payroll Calculation")}</div>
          <button className="btn btn-outline btn-sm" onClick={refetch} disabled={loading}>
            <i className={`ti ${loading ? "ti-loader-2 animate-spin" : "ti-refresh"}`} />
            {loading ? t("Loading…") : t("Refresh")}
          </button>
        </div>

        {loading ? (
          <div style={{ padding: "48px", textAlign: "center", color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 32, display: "block", marginBottom: 12 }} />
            {t("Loading payslips…")}
          </div>
        ) : payslips.length === 0 ? (
          <div style={{ padding: "48px", textAlign: "center", color: "var(--on-variant)" }}>
            <i className="ti ti-file-off" style={{ fontSize: 36, display: "block", marginBottom: 12 }} />
            <div style={{ fontWeight: 600, marginBottom: 6 }}>{t("No payslips found")}</div>
            <div style={{ fontSize: 13 }}>{t("Ensure employees have CTC configured and the cycle was processed in the previous step.")}</div>
          </div>
        ) : (
          <div>
            {payslips.map(p => {
              const isOpen = expanded === p.id;
              return (
                <div key={p.id} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                  <div
                    style={{ display: "flex", alignItems: "center", padding: "14px 20px", cursor: "pointer", gap: 12 }}
                    onClick={() => setExpanded(isOpen ? null : p.id)}
                  >
                    <div style={{ width: 34, height: 34, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700 }}>
                      {p.employee_name.charAt(0)}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600 }}>{p.employee_name}</div>
                      <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{p.department} · {p.branch}</div>
                    </div>
                    <div style={{ textAlign: "right", marginRight: 16 }}>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{t("Gross")}</div>
                      <div style={{ fontWeight: 600 }}>{fmt(p.gross_earnings)}</div>
                    </div>
                    <div style={{ textAlign: "right", marginRight: 16 }}>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{t("Deductions")}</div>
                      <div style={{ fontWeight: 600, color: "var(--error)" }}>{fmt(p.total_deductions)}</div>
                    </div>
                    {(Number(p.bonus ?? 0) + Number(p.reimbursements ?? 0)) > 0 && (
                      <div style={{ textAlign: "right", marginRight: 16 }}>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{t("Extras")}</div>
                        <div style={{ fontWeight: 600, color: "var(--info)" }}>
                          {fmt(Number(p.bonus ?? 0) + Number(p.reimbursements ?? 0))}
                        </div>
                      </div>
                    )}
                    <div style={{ textAlign: "right", marginRight: 20 }}>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{t("Net Pay")}</div>
                      <div style={{ fontWeight: 700, color: "var(--success)", fontSize: 16 }}>{fmt(p.net_pay)}</div>
                    </div>
                    <i className={`ti ${isOpen ? "ti-chevron-up" : "ti-chevron-down"}`} style={{ color: "var(--outline)" }} />
                  </div>

                  {isOpen && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", background: "var(--bg-low)", borderTop: "1px solid var(--outline-v)", padding: "16px 20px" }}>
                      {/* Earnings */}
                      <div style={{ paddingRight: 16 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 10 }}>{t("Earnings")}</div>
                        {[
                          [t("Basic"),           p.basic],
                          [t("HRA"),             p.hra],
                          [t("Special Allow."),  p.special_allowance],
                        ].map(([k, v]) => (
                          <div key={k as string} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
                            <span style={{ color: "var(--on-variant)" }}>+ {k}</span>
                            <span>{fmt(v as string)}</span>
                          </div>
                        ))}
                        <div style={{ borderTop: "1.5px solid var(--outline-v)", paddingTop: 6, marginTop: 6, display: "flex", justifyContent: "space-between", fontWeight: 700 }}>
                          <span>{t("Gross")}</span>
                          <span style={{ color: "var(--primary)" }}>{fmt(p.gross_earnings)}</span>
                        </div>
                      </div>

                      {/* Deductions */}
                      <div style={{ padding: "0 16px", borderLeft: "1px solid var(--outline-v)", borderRight: "1px solid var(--outline-v)" }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 10 }}>{t("Deductions")}</div>
                        {[
                          [t("PF Employee"),   p.pf_employee],
                          [t("ESI Employee"),  p.esi_employee],
                          [t("Prof. Tax"),     p.pt_deduction],
                          [t("LWF"),           p.lwf_employee],
                          [t("LOP Deduction"), p.lop_deduction],
                        ].map(([k, v]) => Number(v) > 0 && (
                          <div key={k as string} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
                            <span style={{ color: "var(--on-variant)" }}>- {k}</span>
                            <span style={{ color: "var(--error)" }}>{fmt(v as string)}</span>
                          </div>
                        ))}
                        <div style={{ borderTop: "1.5px solid var(--outline-v)", paddingTop: 6, marginTop: 6, display: "flex", justifyContent: "space-between", fontWeight: 700 }}>
                          <span>{t("Total Deductions")}</span>
                          <span style={{ color: "var(--error)" }}>{fmt(p.total_deductions)}</span>
                        </div>
                      </div>

                      {/* Net */}
                      <div style={{ paddingLeft: 16 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 10 }}>{t("Net Salary")}</div>
                        {Number(p.bonus ?? 0) > 0 && (
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
                            <span style={{ color: "var(--on-variant)" }}>{t("+ Bonus")}</span>
                            <span style={{ color: "var(--info)" }}>{fmt(p.bonus ?? 0)}</span>
                          </div>
                        )}
                        {Number(p.reimbursements ?? 0) > 0 && (
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
                            <span style={{ color: "var(--on-variant)" }}>{t("+ Reimbursements")}</span>
                            <span style={{ color: "var(--info)" }}>{fmt(p.reimbursements ?? 0)}</span>
                          </div>
                        )}
                        {Number(p.lop_days) > 0 && (
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 13 }}>
                            <span style={{ color: "var(--on-variant)" }}>{t("LOP Days")}</span>
                            <span style={{ color: "var(--error)" }}>{t("{count} days", { count: p.lop_days })}</span>
                          </div>
                        )}
                        <div style={{ background: "rgba(23,144,90,0.07)", borderRadius: "var(--radius)", padding: "10px 12px", marginTop: 10 }}>
                          <div style={{ fontSize: 11, color: "var(--on-variant)", marginBottom: 4 }}>{t("Net Pay")}</div>
                          <div style={{ fontSize: 22, fontWeight: 800, color: "var(--success)" }}>{fmt(p.net_pay)}</div>
                        </div>
                        {/* Employer costs info */}
                        {(Number(p.pf_employer ?? 0) + Number(p.esi_employer ?? 0)) > 0 && (
                          <div style={{ marginTop: 8, fontSize: 11, color: "var(--on-variant)" }}>
                            {t("Employer contribution: {amount}", { amount: fmt(Number(p.pf_employer ?? 0) + Number(p.esi_employer ?? 0)) })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> {t("Back")}</button>
          <button className="btn btn-filled" onClick={onNext} disabled={payslips.length === 0 || loading}>
            {t("Continue")} <i className="ti ti-arrow-right" />
          </button>
        </div>
      </div>
    </div>
  );
}
