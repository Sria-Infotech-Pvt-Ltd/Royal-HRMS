"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { LeaveStats, LEAVE_TYPE_CONFIG } from "../_data";


interface Props { role?: string }

export default function LeaveAnalytics({ role = "employee" }: Props) {
  const isEmployee  = role === "employee";
  const currentYear = new Date().getFullYear();
  // Employees see own stats+balances; approvers see team/branch/org stats (backend auto-scopes by role)
  const statsUrl = isEmployee
    ? API.leave.stats + `?year=${currentYear}&scope=own`
    : API.leave.stats + `?year=${currentYear}`;
  const { data: stats, loading } = useFetch<LeaveStats>(statsUrl);

  if (loading) {
    return (
      <div style={{ padding: "60px 20px", textAlign: "center" }}>
        <i className="ti ti-loader-2" style={{ fontSize: 28, color: "var(--outline-v)" }} />
      </div>
    );
  }

  const totalApproved = stats?.approved  ?? 0;
  const totalPending  = stats?.pending   ?? 0;
  const totalAll      = stats?.total     ?? 0;
  const balances      = stats?.balances  ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Summary stats */}
      <div className="stats-grid" style={{ marginBottom: 0 }}>
        {[
          { label: "Total Requests",   value: totalAll,      icon: "ti-clipboard-list", cls: "si-primary", sub: `This year (${currentYear})` },
          { label: "Approved",         value: totalApproved, icon: "ti-circle-check",   cls: "si-success", sub: `This year (${currentYear})` },
          { label: "Pending Approval", value: totalPending,  icon: "ti-clock",          cls: "si-warn",    sub: `This year (${currentYear})` },
          { label: "Rejected",         value: stats?.rejected ?? 0, icon: "ti-x-circle", cls: "si-error",  sub: `This year (${currentYear})` },
          {
            label: "Loss of Pay (LOP)",
            value: stats?.lop_days ?? 0,
            icon: "ti-coin-off",
            cls: "si-warn",
            sub: `${stats?.lop_requests ?? 0} request${(stats?.lop_requests ?? 0) !== 1 ? "s" : ""} in ${currentYear}`,
          },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
              <div>
                <div className="stat-label">{s.label}</div>
                <div className="stat-value">{s.value}</div>
                <div className="stat-sub">{s.sub}</div>
              </div>
              <div className={`stat-icon ${s.cls}`} style={{ float: "none", margin: 0 }}>
                <i className={`ti ${s.icon}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Leave balance breakdown */}
      {balances.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <i className="ti ti-chart-bar" /> Leave Balance Breakdown
            </div>
          </div>
          <div style={{ padding: "0 20px 20px" }}>
            {balances.map(b => {
              const cfg   = LEAVE_TYPE_CONFIG[b.leave_type];
              const pct   = b.total_days > 0 ? Math.round((b.used_days / b.total_days) * 100) : 0;
              return (
                <div key={b.leave_type} style={{ marginBottom: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 13 }}>
                    <span style={{ fontWeight: 600 }}>{b.leave_type_display}</span>
                    <span style={{ color: "var(--on-variant)" }}>
                      {b.used_days} used / {b.total_days} total — <strong>{b.available} remaining</strong>
                    </span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${pct}%`, background: cfg?.color ?? "var(--primary)" }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Balance empty state — only shown to employees (approvers never receive balance data) */}
      {isEmployee && balances.length === 0 && (
        <div className="card" style={{ padding: "40px 20px", textAlign: "center" }}>
          <i className="ti ti-chart-bar-off" style={{ fontSize: 32, color: "var(--outline-v)", display: "block", marginBottom: 8 }} />
          <p style={{ color: "var(--on-variant)", fontSize: 13 }}>
            No leave balance data for {currentYear}. Contact HR to credit your annual leave.
          </p>
        </div>
      )}

      {/* Status distribution */}
      {totalAll > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-chart-donut" /> Request Status Distribution</div>
          </div>
          <div style={{ padding: "0 20px 20px", display: "flex", flexDirection: "column", gap: 10 }}>
            {[
              { label: "Approved",  value: stats?.approved  ?? 0, color: "var(--success)" },
              { label: "Pending",   value: totalPending,          color: "var(--warn)"    },
              { label: "Rejected",  value: stats?.rejected  ?? 0, color: "var(--error)"   },
              { label: "Cancelled", value: stats?.cancelled ?? 0, color: "var(--outline-v)" },
            ].map(row => {
              const pct = totalAll > 0 ? Math.round((row.value / totalAll) * 100) : 0;
              return (
                <div key={row.label}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                    <span style={{ fontWeight: 500 }}>{row.label}</span>
                    <span style={{ color: "var(--on-variant)" }}>{row.value} ({pct}%)</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${pct}%`, background: row.color }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

    </div>
  );
}
