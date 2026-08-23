"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { EmployeePayslip } from "@/types/payroll";

interface PagedResponse<T> { results: T[]; count: number }

interface Props { employeeId: string }

const INR = (n: string | number) =>
  `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

const fmtMonth = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { month: "short", year: "numeric" });

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

const STATUS_BADGE: Record<EmployeePayslip["status"], string> = {
  draft:        "badge badge-neutral",
  sent:         "badge badge-info",
  acknowledged: "badge badge-info",
  queried:      "badge badge-warn",
  resolved:     "badge badge-info",
  paid:         "badge badge-success",
};

const STATUS_LABEL: Record<EmployeePayslip["status"], string> = {
  draft:        "Processing",
  sent:         "Sent",
  acknowledged: "Acknowledged",
  queried:      "Query Raised",
  resolved:     "Query Resolved",
  paid:         "Paid",
};

export default function PayrollTab({ employeeId }: Props) {
  const { data, loading, error } = useFetch<PagedResponse<EmployeePayslip>>(
    employeeId ? API.payroll.employeePayslipHistory(employeeId) : null
  );
  const payslips = data?.results ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-report-money" />Payslip History</span>
      </div>

      {error && <div className="alert alert-error" style={{ margin: 20 }}>{error}</div>}

      {loading ? (
        <div className="empty-state"><i className="ti ti-loader-2" /><h3>Loading…</h3></div>
      ) : payslips.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-report-money" />
          <h3>No payslips yet</h3>
          <p>Payslips will appear here once payroll has been processed for this employee.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Period</th>
                <th>Pay Date</th>
                <th>Structure</th>
                <th>Gross</th>
                <th>Deductions</th>
                <th>Net Pay</th>
                <th>Status</th>
                <th>Payslip</th>
              </tr>
            </thead>
            <tbody>
              {payslips.map(p => (
                <tr key={p.id}>
                  <td>{fmtMonth(p.cycle_start)}</td>
                  <td>{fmtDate(p.pay_date)}</td>
                  <td>{p.structure_name ?? <span style={{ color: "var(--on-variant)" }}>Default</span>}</td>
                  <td style={{ fontVariantNumeric: "tabular-nums" }}>{INR(p.gross_earnings)}</td>
                  <td style={{ fontVariantNumeric: "tabular-nums" }}>{INR(p.total_deductions)}</td>
                  <td style={{ fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>{INR(p.net_pay)}</td>
                  <td><span className={STATUS_BADGE[p.status]}>{STATUS_LABEL[p.status]}</span></td>
                  <td>
                    {p.payslip_pdf ? (
                      <a href={p.payslip_pdf} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm">
                        <i className="ti ti-download" /> Download
                      </a>
                    ) : (
                      <span style={{ color: "var(--on-variant)", fontSize: 12 }}>Not available</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
