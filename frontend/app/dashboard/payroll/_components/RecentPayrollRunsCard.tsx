"use client";

import { useRouter } from "next/navigation";
import type { PayrollCycle } from "@/types/payroll";
import { STATUS_BADGE, STATUS_LABEL, DETAIL_STATUSES, TERMINAL_STATUSES, cyclePeriodLabel } from "./payrollDashboardShared";
import { formatDate } from "@/lib/formatDate";
import { useT } from "@/hooks/useI18n";

interface RecentPayrollRunsCardProps {
  cycles: PayrollCycle[];
  cyclesLoading: boolean;
  canResume: boolean;
  onRunPayroll: (month?: string, year?: string) => void;
  onResumeCycle: (id: string, status: string, cycleStart?: string) => void;
}

export default function RecentPayrollRunsCard({ cycles, cyclesLoading, canResume, onRunPayroll, onResumeCycle }: RecentPayrollRunsCardProps) {
  const router = useRouter();
  const t = useT();

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-history" /> {t("Recent Payroll Runs")}</div>
      </div>

      {cyclesLoading ? (
        <div style={{ padding: "40px", textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 24 }} />
          <div style={{ marginTop: 8, fontSize: 13 }}>{t("Loading payroll cycles…")}</div>
        </div>
      ) : cycles.length === 0 ? (
        <div style={{ padding: "40px", textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-calendar-off" style={{ fontSize: 36, display: "block", marginBottom: 12 }} />
          <div style={{ fontWeight: 600, marginBottom: 4 }}>{t("No payroll runs yet")}</div>
          <div style={{ fontSize: 13, marginBottom: 16 }}>{t("Click \"Run Payroll\" to start your first payroll cycle.")}</div>
          <button className="btn btn-filled btn-sm" onClick={() => onRunPayroll()}>
            <i className="ti ti-player-play" /> {t("Run First Payroll")}
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t("Period")}</th>
                <th>{t("Cycle Start")}</th>
                <th>{t("Cycle End")}</th>
                <th>{t("Pay Date")}</th>
                <th>{t("Payslips")}</th>
                <th>{t("Status")}</th>
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
                    {cyclePeriodLabel(c)}
                  </td>
                  <td style={{ fontSize: 13 }}>{formatDate(c.cycle_start)}</td>
                  <td style={{ fontSize: 13 }}>{formatDate(c.cycle_end)}</td>
                  <td style={{ fontSize: 13, fontWeight: 500 }}>{formatDate(c.pay_date)}</td>
                  <td>
                    <span style={{ fontWeight: 600 }}>{c.payslip_count}</span>
                    <span style={{ color: "var(--on-variant)", fontSize: 12 }}> {t("employees")}</span>
                  </td>
                  <td>
                    <span className={STATUS_BADGE[c.status] ?? "badge badge-neutral"}>
                      {STATUS_LABEL[c.status] ? t(STATUS_LABEL[c.status]) : c.status}
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
