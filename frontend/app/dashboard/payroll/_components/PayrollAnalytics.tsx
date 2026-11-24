"use client";

import { useFetch } from "@/hooks/useFetch";
import { useT } from "@/hooks/useI18n";
import { API } from "@/lib/api/endpoints";
import type { PayrollCycle } from "@/types/payroll";
import { cyclePeriodLabel } from "./payrollDashboardShared";
import { formatDate } from "@/lib/formatDate";

interface PagedResponse<T> { results: T[]; count: number; }

const MONTHS_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];


function BarChart({ data, max, color }: { data: { label: string; value: number }[]; max: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 120, padding: "0 4px" }}>
      {data.map((d, i) => {
        const pct = max > 0 ? (d.value / max) * 100 : 0;
        return (
          <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1, gap: 4 }}>
            <div style={{ fontSize: 10, color: "var(--on-variant)", fontWeight: 600 }}>{d.value}</div>
            <div style={{ width: "100%", background: color, borderRadius: "3px 3px 0 0", height: `${Math.max(pct, 4)}%`, transition: "height 0.3s" }} />
            <div style={{ fontSize: 10, color: "var(--on-variant)" }}>{d.label}</div>
          </div>
        );
      })}
    </div>
  );
}

const STATUS_COLOR: Record<string, string> = {
  paid:                "var(--success)",
  closed:              "var(--success)",
  draft:               "var(--outline)",
  attendance_pending:  "var(--warn)",
  attendance_approved: "var(--info)",
  processing:          "var(--info)",
  payslips_generated:  "var(--primary)",
  query_window_open:   "var(--primary)",
};

const STATUS_LABEL: Record<string, string> = {
  paid:                "Paid",
  closed:              "Closed",
  draft:               "Draft",
  attendance_pending:  "Pending Approval",
  attendance_approved: "Approved",
  processing:          "Processing",
  payslips_generated:  "Payslips Ready",
  query_window_open:   "Query Window",
};

function EmptyChart({ message }: { message: string }) {
  return (
    <div style={{ height: 120, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 6, color: "var(--on-variant)" }}>
      <i className="ti ti-chart-bar" style={{ fontSize: 24, opacity: 0.4 }} />
      <span style={{ fontSize: 12, textAlign: "center" }}>{message}</span>
    </div>
  );
}

export default function PayrollAnalytics() {
  const t = useT();
  const { data: cyclesPage, loading } =
    useFetch<PagedResponse<PayrollCycle>>(API.payroll.cycles);

  const cycles = cyclesPage?.results ?? [];

  const totalPayslips = cycles.reduce((s, c) => s + (c.payslip_count ?? 0), 0);
  const paidCycles    = cycles.filter(c => ["paid", "closed"].includes(c.status));
  const latestCycle   = cycles[0] ?? null;

  // Group cycles by month for headcount bar chart
  const byMonth = new Map<string, number>();
  for (const c of cycles) {
    const d = new Date(c.cycle_start);
    const key = `${MONTHS_SHORT[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`;
    byMonth.set(key, (byMonth.get(key) ?? 0) + (c.payslip_count ?? 0));
  }
  const monthlyData = [...byMonth.entries()].map(([label, value]) => ({ label, value }));
  const maxMonthly  = Math.max(...monthlyData.map(d => d.value), 1);

  // Status distribution
  const statusCounts = new Map<string, number>();
  for (const c of cycles) {
    statusCounts.set(c.status, (statusCounts.get(c.status) ?? 0) + 1);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* KPI row */}
      <div className="stats-grid" style={{ marginBottom: 0 }}>
        {[
          {
            label: t("Total Payslips Issued"),
            value: loading ? "—" : String(totalPayslips),
            sub: cycles.length === 1 ? t("across {count} payroll run", { count: cycles.length }) : t("across {count} payroll runs", { count: cycles.length }),
            icon: "ti-file-invoice",
            cls: "si-primary",
          },
          {
            label: t("Completed Runs"),
            value: loading ? "—" : String(paidCycles.length),
            sub: t("Paid or closed"),
            icon: "ti-circle-check",
            cls: "si-success",
          },
          {
            label: t("Latest Pay Date"),
            value: loading ? "—" : (latestCycle?.pay_date ?? "—"),
            sub: latestCycle ? (STATUS_LABEL[latestCycle.status] ? t(STATUS_LABEL[latestCycle.status]) : latestCycle.status) : t("No cycles yet"),
            icon: "ti-calendar-event",
            cls: "si-info",
          },
          {
            label: t("Avg. Payslips / Run"),
            value: loading || cycles.length === 0 ? "—" : String(Math.round(totalPayslips / cycles.length)),
            sub: t("Employees processed"),
            icon: "ti-users",
            cls: "si-primary",
          },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div className="stat-label">{s.label}</div>
                <div className="stat-value" style={{ fontSize: 22 }}>{s.value}</div>
                <div className="stat-sub">{s.sub}</div>
              </div>
              <div className={`stat-icon ${s.cls}`} style={{ float: "none", margin: 0 }}>
                <i className={`ti ${s.icon}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Monthly headcount + Status breakdown */}
      <div className="payroll-chart-row" style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-chart-bar" /> {t("Employees Processed per Payroll Run")}</div>
          </div>
          <div className="card-body">
            {loading ? (
              <EmptyChart message={t("Loading…")} />
            ) : monthlyData.length === 0 ? (
              <EmptyChart message={t("No payroll cycles yet. Data appears here after your first run.")} />
            ) : (
              <BarChart data={monthlyData} max={maxMonthly} color="var(--primary)" />
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-chart-donut" /> {t("Cycle Status")}</div>
          </div>
          <div className="card-body">
            {loading ? (
              <div style={{ padding: 20, textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>{t("Loading…")}</div>
            ) : cycles.length === 0 ? (
              <div style={{ padding: 20, textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>{t("No data yet")}</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[...statusCounts.entries()].map(([status, count]) => {
                  const pct = Math.round((count / cycles.length) * 100);
                  return (
                    <div key={status}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
                        <span style={{ fontWeight: 500 }}>{STATUS_LABEL[status] ? t(STATUS_LABEL[status]) : status}</span>
                        <span style={{ color: "var(--on-variant)" }}>{count === 1 ? t("{count} cycle", { count }) : t("{count} cycles", { count })}</span>
                      </div>
                      <div style={{ height: 6, background: "var(--bg-low)", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${pct}%`, background: STATUS_COLOR[status] ?? "var(--outline)", borderRadius: 3, transition: "width 0.4s" }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent cycles list */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-history" /> {t("All Payroll Cycles")}</div>
        </div>
        {loading ? (
          <div style={{ padding: "32px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
            <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 20, display: "block", marginBottom: 8 }} />
            {t("Loading…")}
          </div>
        ) : cycles.length === 0 ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--on-variant)" }}>
            <i className="ti ti-chart-off" style={{ fontSize: 32, display: "block", marginBottom: 12 }} />
            <div style={{ fontWeight: 600 }}>{t("No analytics yet")}</div>
            <div style={{ fontSize: 13, marginTop: 4 }}>{t("Analytics populate automatically as you run and complete payroll cycles.")}</div>
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
                  <th style={{ textAlign: "right" }}>{t("Employees")}</th>
                  <th>{t("Status")}</th>
                </tr>
              </thead>
              <tbody>
                {cycles.map(c => (
                  <tr key={c.id}>
                    <td style={{ fontWeight: 600 }}>
                      {cyclePeriodLabel(c)}
                    </td>
                    <td style={{ fontSize: 13 }}>{formatDate(c.cycle_start)}</td>
                    <td style={{ fontSize: 13 }}>{formatDate(c.cycle_end)}</td>
                    <td style={{ fontWeight: 500 }}>{formatDate(c.pay_date)}</td>
                    <td style={{ textAlign: "right", fontWeight: 600 }}>{c.payslip_count}</td>
                    <td>
                      <span style={{ fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 999, background: `${STATUS_COLOR[c.status] ?? "var(--outline)"}22`, color: STATUS_COLOR[c.status] ?? "var(--on-variant)" }}>
                        {STATUS_LABEL[c.status] ? t(STATUS_LABEL[c.status]) : c.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Note about advanced analytics */}
      <div className="alert alert-info">
        <i className="ti ti-info-circle" />
        <span>{t("Gross/net payroll trends, department breakdowns, and overtime cost charts will be available once dedicated analytics endpoints are built. The data above is computed live from your payroll cycle records.")}</span>
      </div>

      <style jsx>{`
        @media (max-width: 768px) {
          .payroll-chart-row {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
