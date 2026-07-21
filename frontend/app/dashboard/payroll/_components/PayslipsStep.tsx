"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { EmployeePayslip, PayrollCycle } from "@/types/payroll";

interface Props {
  cycleId: string;
  onNext: () => void;
  onBack: () => void;
}

interface PagedResponse<T> { results: T[]; count: number; }

type SlipStatus = EmployeePayslip["status"];

const STATUS_STYLE: Record<SlipStatus, { bg: string; text: string; label: string }> = {
  draft:        { bg: "bg-gray-50",    text: "text-gray-600",    label: "Draft"        },
  sent:         { bg: "bg-blue-50",    text: "text-blue-700",    label: "Dispatched"   },
  acknowledged: { bg: "bg-indigo-50",  text: "text-indigo-700",  label: "Acknowledged" },
  queried:      { bg: "bg-amber-50",   text: "text-amber-700",   label: "Queried"      },
  resolved:     { bg: "bg-emerald-50", text: "text-emerald-700", label: "Resolved"     },
  paid:         { bg: "bg-green-50",   text: "text-green-700",   label: "Paid"         },
};

const fmt = (n: number | string) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

export default function PayslipsStep({ cycleId, onNext, onBack }: Props) {
  const { data: payslipPage, loading, refetch } =
    useFetch<PagedResponse<EmployeePayslip>>(API.payroll.cyclePayslips(cycleId));
  const { data: cycle } = useFetch<PayrollCycle>(API.payroll.cycle(cycleId));

  const [dispatching, setDispatching] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const payslips  = payslipPage?.results ?? [];
  const totalNet  = payslips.reduce((s, p) => s + Number(p.net_pay), 0);
  const allSent   = payslips.length > 0 && payslips.every(p => p.status !== "draft");
  const cycleDispatched = cycle?.status === "query_window_open" || allSent;

  async function dispatch() {
    setDispatching(true);
    setErr(null);
    try {
      await clientApi.post(API.payroll.dispatchPayslips(cycleId));
      refetch();
    } catch (error: unknown) {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? "Failed to dispatch payslips.";
      setErr(msg);
    } finally {
      setDispatching(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div className="card">
        <div className="card-header">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: "var(--radius)", background: "var(--bg-low)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <i className="ti ti-file-invoice" style={{ fontSize: 18, color: "var(--primary)" }} />
            </div>
            <div>
              <div className="card-title">Dispatch Payslips</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
                {payslips.length} employees · Net: <strong style={{ color: "var(--success)" }}>{fmt(totalNet)}</strong>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {cycleDispatched ? (
              <span className="badge badge-success"><i className="ti ti-check" /> Dispatched</span>
            ) : (
              <button
                className="btn btn-filled btn-sm"
                onClick={dispatch}
                disabled={dispatching || payslips.length === 0}
              >
                {dispatching
                  ? <><i className="ti ti-loader-2 animate-spin" /> Dispatching…</>
                  : <><i className="ti ti-send" /> Dispatch All</>}
              </button>
            )}
            <button className="btn btn-ghost btn-sm" onClick={refetch}><i className="ti ti-refresh" /></button>
          </div>
        </div>

        {err && (
          <div className="alert alert-error" style={{ margin: "0", borderRadius: 0 }}>
            <i className="ti ti-alert-circle" />
            <span>{err}</span>
          </div>
        )}

        {cycleDispatched && (
          <div className="alert alert-success" style={{ margin: "0", borderRadius: 0 }}>
            <i className="ti ti-circle-check" />
            <span>All payslips dispatched. Employees have {cycle?.query_window_closes_at ? `until ${new Date(cycle.query_window_closes_at).toLocaleDateString("en-IN")}` : "the configured window"} to raise queries.</span>
          </div>
        )}

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
                  <th style={{ textAlign: "right" }}>Gross</th>
                  <th style={{ textAlign: "right" }}>Deductions</th>
                  <th style={{ textAlign: "right" }}>Net Salary</th>
                  <th>Status</th>
                  <th>Sent At</th>
                </tr>
              </thead>
              <tbody>
                {payslips.map(p => {
                  const style = STATUS_STYLE[p.status];
                  return (
                    <tr key={p.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}>
                            {p.employee_name.charAt(0)}
                          </div>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: 13 }}>{p.employee_name}</div>
                            <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.department}</div>
                          </div>
                        </div>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 600 }}>{fmt(p.gross_earnings)}</td>
                      <td style={{ textAlign: "right", color: "var(--error)" }}>{fmt(p.total_deductions)}</td>
                      <td style={{ textAlign: "right", fontWeight: 700, color: "var(--success)" }}>{fmt(p.net_pay)}</td>
                      <td>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${style.bg} ${style.text}`}>
                          {style.label}
                        </span>
                      </td>
                      <td style={{ fontSize: 11, color: "var(--on-variant)" }}>
                        {p.sent_at
                          ? new Date(p.sent_at).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              {payslips.length > 0 && (
                <tfoot>
                  <tr style={{ background: "var(--bg-low)", borderTop: "2px solid var(--outline-v)" }}>
                    <td style={{ fontWeight: 700 }}>Total ({payslips.length} employees)</td>
                    <td style={{ textAlign: "right", fontWeight: 700 }}>{fmt(payslips.reduce((s, p) => s + Number(p.gross_earnings), 0))}</td>
                    <td style={{ textAlign: "right", fontWeight: 700, color: "var(--error)" }}>{fmt(payslips.reduce((s, p) => s + Number(p.total_deductions), 0))}</td>
                    <td style={{ textAlign: "right", fontWeight: 800, color: "var(--success)", fontSize: 15 }}>{fmt(totalNet)}</td>
                    <td colSpan={2} />
                  </tr>
                </tfoot>
              )}
            </table>

            {payslips.length === 0 && (
              <div style={{ padding: "32px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                No payslips found for this cycle.
              </div>
            )}
          </div>
        )}

        <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
          <button
            className="btn btn-filled"
            onClick={onNext}
            disabled={!cycleDispatched}
            style={{ opacity: cycleDispatched ? 1 : 0.5 }}
          >
            Continue to Mark as Paid <i className="ti ti-arrow-right" />
          </button>
        </div>
      </div>
    </div>
  );
}
