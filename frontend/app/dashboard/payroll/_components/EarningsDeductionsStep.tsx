"use client";

import { Fragment, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { EmployeePayslip, ProcessPayrollResult } from "@/types/payroll";

interface Props {
  cycleId: string;
  onNext: () => void;
  onBack: () => void;
}

interface PagedResponse<T> { results: T[]; count: number; }

const fmt = (n: number | string) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

export default function EarningsDeductionsStep({ cycleId, onNext, onBack }: Props) {
  const [processing, setProcessing] = useState(false);
  const [processed, setProcessed]   = useState(false);
  const [processErr, setProcessErr] = useState<string | null>(null);
  const [expanded, setExpanded]     = useState<string | null>(null);
  const [skipped, setSkipped]       = useState<string[]>([]);

  const { data: payslipPage, loading, refetch } =
    useFetch<PagedResponse<EmployeePayslip>>(
      processed ? API.payroll.cyclePayslips(cycleId) : null
    );

  const payslips = payslipPage?.results ?? [];

  async function runProcess() {
    setProcessing(true);
    setProcessErr(null);
    try {
      const res = await clientApi.post<{ data: ProcessPayrollResult }>(API.payroll.processCycle(cycleId));
      setSkipped(res.data.data.skipped ?? []);
      setProcessed(true);
    } catch (error: unknown) {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? "Failed to process payroll. Check that the cycle is approved.";
      setProcessErr(msg);
    } finally {
      setProcessing(false);
    }
  }

  const totalGross = payslips.reduce((s, p) => s + Number(p.gross_earnings), 0);
  const totalDed   = payslips.reduce((s, p) => s + Number(p.total_deductions), 0);
  const totalNet   = payslips.reduce((s, p) => s + Number(p.net_pay), 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Process trigger card */}
      {!processed && (
        <div className="card">
          <div className="card-body" style={{ textAlign: "center", padding: "40px 20px" }}>
            <i className="ti ti-calculator" style={{ fontSize: 44, color: "var(--primary)", display: "block", marginBottom: 12 }} />
            <h3 style={{ marginBottom: 8, color: "var(--on-bg)" }}>Compute Payroll</h3>
            <p style={{ color: "var(--on-variant)", marginBottom: 20, maxWidth: 440, margin: "0 auto 20px" }}>
              This will calculate salaries for all eligible employees using their CTC, salary structure, and statutory rules for each branch.
            </p>

            {processErr && (
              <div className="alert alert-error" style={{ marginBottom: 16, textAlign: "left" }}>
                <i className="ti ti-alert-circle" />
                <span>{processErr}</span>
              </div>
            )}

            <button
              className="btn btn-filled"
              onClick={runProcess}
              disabled={processing}
              style={{ minWidth: 180 }}
            >
              {processing
                ? <><i className="ti ti-loader-2 animate-spin" /> Computing…</>
                : <><i className="ti ti-calculator" /> Compute Salaries</>}
            </button>
          </div>
        </div>
      )}

      {/* Results */}
      {processed && (
        <>
          {skipped.length > 0 && (
            <div className="alert alert-warn" style={{ alignItems: "flex-start" }}>
              <i className="ti ti-alert-triangle" />
              <span>
                {skipped.length} employee{skipped.length > 1 ? "s were" : " was"} skipped — no salary structure or CTC configured: {skipped.join(", ")}.
                Set up their salary in Employees → Salary tab, then reprocess to include them.
              </span>
            </div>
          )}

          {/* Summary row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
            <div className="stat-card">
              <div className="stat-label">Total Gross</div>
              <div className="stat-value" style={{ color: "var(--primary)" }}>{fmt(totalGross)}</div>
              <div className="stat-sub">{payslips.length} employees</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total Deductions</div>
              <div className="stat-value" style={{ color: "var(--error)" }}>{fmt(totalDed)}</div>
              <div className="stat-sub">PF + ESI + PT + LWF</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Net Payable</div>
              <div className="stat-value" style={{ color: "var(--success)" }}>{fmt(totalNet)}</div>
              <div className="stat-sub">Gross − Deductions</div>
            </div>
          </div>

          {/* Earnings table */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-cash" /> Earnings Breakdown</div>
              <button className="btn btn-outline btn-sm" onClick={refetch}>
                <i className="ti ti-refresh" /> Refresh
              </button>
            </div>

            {loading ? (
              <div style={{ padding: "32px", textAlign: "center", color: "var(--on-variant)" }}>
                <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 24 }} />
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th style={{ textAlign: "right" }}>Basic</th>
                      <th style={{ textAlign: "right" }}>HRA</th>
                      <th style={{ textAlign: "right" }}>Spl. Allow.</th>
                      <th style={{ textAlign: "right" }}>LOP Days</th>
                      <th style={{ textAlign: "right", color: "var(--success)" }}>Gross</th>
                      <th style={{ textAlign: "right", color: "var(--error)" }}>Deductions</th>
                      <th style={{ textAlign: "right", color: "var(--success)" }}>Net Pay</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {payslips.map(p => {
                      const isOpen = expanded === p.id;
                      return (
                        <Fragment key={p.id}>
                          <tr style={{ cursor: "pointer" }} onClick={() => setExpanded(isOpen ? null : p.id)}>
                            <td>
                              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}>
                                  {p.employee_name.charAt(0)}
                                </div>
                                <div>
                                  <div style={{ fontWeight: 600, fontSize: 13 }}>{p.employee_name}</div>
                                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.department} · {p.branch}</div>
                                </div>
                              </div>
                            </td>
                            <td style={{ textAlign: "right", fontSize: 13 }}>{fmt(p.basic)}</td>
                            <td style={{ textAlign: "right", fontSize: 13 }}>{fmt(p.hra)}</td>
                            <td style={{ textAlign: "right", fontSize: 13 }}>{fmt(p.special_allowance)}</td>
                            <td style={{ textAlign: "right", fontSize: 13, color: Number(p.lop_days) > 0 ? "var(--error)" : "var(--on-variant)" }}>
                              {Number(p.lop_days) > 0 ? p.lop_days : "—"}
                            </td>
                            <td style={{ textAlign: "right", fontWeight: 700, color: "var(--success)" }}>{fmt(p.gross_earnings)}</td>
                            <td style={{ textAlign: "right", fontWeight: 600, color: "var(--error)" }}>{fmt(p.total_deductions)}</td>
                            <td style={{ textAlign: "right", fontWeight: 700, color: "var(--success)", fontSize: 14 }}>{fmt(p.net_pay)}</td>
                            <td>
                              <i className={`ti ${isOpen ? "ti-chevron-up" : "ti-chevron-down"}`} style={{ color: "var(--outline)" }} />
                            </td>
                          </tr>
                          {isOpen && (
                            <tr key={`${p.id}-detail`} style={{ background: "var(--bg-low)" }}>
                              <td colSpan={9} style={{ padding: "0" }}>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0, padding: "16px 20px" }}>
                                  {/* Deduction detail */}
                                  <div>
                                    <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 8 }}>Statutory Deductions</div>
                                    {[
                                      ["PF (Employee)", p.pf_employee],
                                      ["ESI (Employee)", p.esi_employee],
                                      ["Professional Tax", p.pt_deduction],
                                      ["LWF (Employee)", p.lwf_employee],
                                      ["LOP Deduction", p.lop_deduction],
                                    ].map(([label, val]) => Number(val) > 0 && (
                                      <div key={label as string} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 13 }}>
                                        <span style={{ color: "var(--on-variant)" }}>- {label}</span>
                                        <span style={{ color: "var(--error)" }}>{fmt(val as string)}</span>
                                      </div>
                                    ))}
                                  </div>
                                  {/* Employer contributions */}
                                  <div style={{ paddingLeft: 20, borderLeft: "1px solid var(--outline-v)" }}>
                                    <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 8 }}>Employer Contributions</div>
                                    {[
                                      ["PF (Employer)", p.pf_employer],
                                      ["ESI (Employer)", p.esi_employer],
                                      ["LWF (Employer)", p.lwf_employer],
                                    ].map(([label, val]) => Number(val) > 0 && (
                                      <div key={label as string} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 13 }}>
                                        <span style={{ color: "var(--on-variant)" }}>{label}</span>
                                        <span style={{ color: "var(--info)" }}>{fmt(val as string)}</span>
                                      </div>
                                    ))}
                                    <div style={{ marginTop: 12, padding: "8px 12px", background: "rgba(27,138,107,0.06)", borderRadius: "var(--radius)" }}>
                                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Net Pay Payable</div>
                                      <div style={{ fontWeight: 800, fontSize: 18, color: "var(--success)" }}>{fmt(p.net_pay)}</div>
                                    </div>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                    {payslips.length > 0 && (
                      <tr style={{ background: "var(--bg-low)" }}>
                        <td style={{ fontWeight: 700 }}>Total</td>
                        <td style={{ textAlign: "right", fontWeight: 600 }}>{fmt(payslips.reduce((s, p) => s + Number(p.basic), 0))}</td>
                        <td style={{ textAlign: "right", fontWeight: 600 }}>{fmt(payslips.reduce((s, p) => s + Number(p.hra), 0))}</td>
                        <td style={{ textAlign: "right", fontWeight: 600 }}>{fmt(payslips.reduce((s, p) => s + Number(p.special_allowance), 0))}</td>
                        <td />
                        <td style={{ textAlign: "right", fontWeight: 700, color: "var(--success)" }}>{fmt(totalGross)}</td>
                        <td style={{ textAlign: "right", fontWeight: 700, color: "var(--error)" }}>{fmt(totalDed)}</td>
                        <td style={{ textAlign: "right", fontWeight: 700, color: "var(--success)" }}>{fmt(totalNet)}</td>
                        <td />
                      </tr>
                    )}
                  </tbody>
                </table>

                {payslips.length === 0 && !loading && (
                  <div style={{ padding: "32px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                    No payslips found. Employees may be missing CTC or salary structure.
                  </div>
                )}
              </div>
            )}

            <div style={{ padding: "14px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
              <button className="btn btn-filled" onClick={onNext} disabled={payslips.length === 0}>
                Continue <i className="ti ti-arrow-right" />
              </button>
            </div>
          </div>
        </>
      )}

      {!processed && (
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 4 }}>
          <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
        </div>
      )}
    </div>
  );
}
