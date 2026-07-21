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

const fmt = (n: number | string) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

export default function BankTransferStep({ cycleId, onNext, onBack }: Props) {
  const { data: payslipPage, loading, refetch } =
    useFetch<PagedResponse<EmployeePayslip>>(API.payroll.cyclePayslips(cycleId));
  const { data: cycle, refetch: refetchCycle } = useFetch<PayrollCycle>(API.payroll.cycle(cycleId));

  const [marking, setMarking] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const payslips = payslipPage?.results ?? [];
  const totalNet = payslips.reduce((s, p) => s + Number(p.net_pay), 0);
  const isPaid   = cycle?.status === "paid" || cycle?.status === "closed";

  async function markPaid() {
    setMarking(true);
    setErr(null);
    try {
      await clientApi.post(API.payroll.markPaid(cycleId));
      refetch();
      refetchCycle();
    } catch (error: unknown) {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? "Failed to mark as paid.";
      setErr(msg);
    } finally {
      setMarking(false);
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-circle-check" /> Mark Payroll as Paid</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="badge badge-primary">{fmt(totalNet)} total</span>
          {isPaid && <span className="badge badge-success"><i className="ti ti-check" /> Paid</span>}
        </div>
      </div>

      {isPaid && (
        <div className="alert alert-success" style={{ margin: "0", borderRadius: 0 }}>
          <i className="ti ti-circle-check" />
          <span>All salaries marked as paid. Payroll run for this cycle is complete.</span>
        </div>
      )}

      {err && (
        <div className="alert alert-error" style={{ margin: "0", borderRadius: 0 }}>
          <i className="ti ti-alert-circle" />
          <span>{err}</span>
        </div>
      )}

      {/* Summary */}
      <div style={{ padding: "20px", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, borderBottom: "1px solid var(--outline-v)" }}>
        <div className="stat-card">
          <div className="stat-label">Employees</div>
          <div className="stat-value">{payslips.length}</div>
          <div className="stat-sub">In this payroll run</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Net Payable</div>
          <div className="stat-value" style={{ color: "var(--success)" }}>{fmt(totalNet)}</div>
          <div className="stat-sub">Gross − all deductions</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Status</div>
          <div className="stat-value" style={{ color: isPaid ? "var(--success)" : "var(--warn)", fontSize: 18 }}>
            {isPaid ? "Paid" : "Pending"}
          </div>
          <div className="stat-sub">{cycle?.pay_date ? `Pay date: ${cycle.pay_date}` : "—"}</div>
        </div>
      </div>

      {/* Payslip list */}
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
                <th>Department</th>
                <th>Branch</th>
                <th style={{ textAlign: "right", color: "var(--success)" }}>Net Salary</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {payslips.map(p => (
                <tr key={p.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}>
                        {p.employee_name.charAt(0)}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{p.employee_name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.employee_id_code}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ fontSize: 13 }}>{p.department || "—"}</td>
                  <td style={{ fontSize: 13 }}>{p.branch || "—"}</td>
                  <td style={{ textAlign: "right", fontWeight: 700, color: "var(--success)", fontSize: 14 }}>{fmt(p.net_pay)}</td>
                  <td>
                    <span className={`badge ${p.status === "paid" ? "badge-success" : "badge-info"}`}>
                      {p.status.charAt(0).toUpperCase() + p.status.slice(1)}
                    </span>
                  </td>
                </tr>
              ))}
              {payslips.length > 0 && (
                <tr style={{ background: "var(--bg-low)" }}>
                  <td style={{ fontWeight: 700 }} colSpan={3}>Total Net Payable</td>
                  <td style={{ textAlign: "right", fontWeight: 800, color: "var(--success)", fontSize: 15 }}>{fmt(totalNet)}</td>
                  <td />
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 8 }}>
          {!isPaid && (
            <button
              className="btn btn-success"
              onClick={markPaid}
              disabled={marking || payslips.length === 0}
            >
              {marking
                ? <><i className="ti ti-loader-2 animate-spin" /> Marking Paid…</>
                : <><i className="ti ti-checks" /> Mark All Paid</>}
            </button>
          )}
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-ghost" onClick={onBack} disabled={isPaid}>
            <i className="ti ti-arrow-left" /> Back
          </button>
          <button
            className="btn btn-filled"
            onClick={onNext}
            disabled={!isPaid}
            style={{ opacity: isPaid ? 1 : 0.5 }}
          >
            <i className="ti ti-circle-check" /> Finish Payroll Run
          </button>
        </div>
      </div>
    </div>
  );
}
