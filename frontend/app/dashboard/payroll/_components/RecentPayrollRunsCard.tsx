"use client";

import { useRouter } from "next/navigation";
import type { PayrollCycle } from "@/types/payroll";
import { STATUS_BADGE, STATUS_LABEL, DETAIL_STATUSES, TERMINAL_STATUSES } from "./payrollDashboardShared";

interface RecentPayrollRunsCardProps {
  cycles: PayrollCycle[];
  cyclesLoading: boolean;
  canResume: boolean;
  onRunPayroll: (month?: string, year?: string) => void;
  onResumeCycle: (id: string, status: string, cycleStart?: string) => void;
}

export default function RecentPayrollRunsCard({ cycles, cyclesLoading, canResume, onRunPayroll, onResumeCycle }: RecentPayrollRunsCardProps) {
  const router = useRouter();

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-history" /> Recent Payroll Runs</div>
      </div>

      {cyclesLoading ? (
        <div style={{ padding: "40px", textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 24 }} />
          <div style={{ marginTop: 8, fontSize: 13 }}>Loading payroll cycles…</div>
        </div>
      ) : cycles.length === 0 ? (
        <div style={{ padding: "40px", textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-calendar-off" style={{ fontSize: 36, display: "block", marginBottom: 12 }} />
          <div style={{ fontWeight: 600, marginBottom: 4 }}>No payroll runs yet</div>
          <div style={{ fontSize: 13, marginBottom: 16 }}>Click &quot;Run Payroll&quot; to start your first payroll cycle.</div>
          <button className="btn btn-filled btn-sm" onClick={() => onRunPayroll()}>
            <i className="ti ti-player-play" /> Run First Payroll
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Period</th>
                <th>Cycle Start</th>
                <th>Cycle End</th>
                <th>Pay Date</th>
                <th>Payslips</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {cycles.map(c => {
                const isDetail   = DETAIL_STATUSES.has(c.status);
                const isTerminal = TERMINAL_STATUSES.has(c.status);
                const handleClick = isDetail
                  ? () => router.push(`/dashboard/payroll/runs/${c.id}`)
                  : !isTerminal && canResume ? () => onResumeCycle(c.id, c.status, c.cycle_start) : undefined;
                return (
                <tr key={c.id} style={{ cursor: handleClick ? "pointer" : "default" }} onClick={handleClick}>
                  <td style={{ fontWeight: 600, fontSize: 13 }}>
                    {new Date(c.cycle_start).toLocaleString("en-IN", { month: "long", year: "numeric" })}
                  </td>
                  <td style={{ fontSize: 13 }}>{c.cycle_start}</td>
                  <td style={{ fontSize: 13 }}>{c.cycle_end}</td>
                  <td style={{ fontSize: 13, fontWeight: 500 }}>{c.pay_date}</td>
                  <td>
                    <span style={{ fontWeight: 600 }}>{c.payslip_count}</span>
                    <span style={{ color: "var(--on-variant)", fontSize: 12 }}> employees</span>
                  </td>
                  <td>
                    <span className={STATUS_BADGE[c.status] ?? "badge badge-neutral"}>
                      {STATUS_LABEL[c.status] ?? c.status}
                    </span>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
