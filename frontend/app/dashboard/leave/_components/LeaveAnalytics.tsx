"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { LeaveStats, LEAVE_TYPE_CONFIG } from "../_data";

export default function LeaveAnalytics() {
  const currentYear = new Date().getFullYear();
  const { data: stats, loading } = useFetch<LeaveStats>(API.leave.stats + `?year=${currentYear}`);

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
          { label: "Total Requests",   value: totalAll,      icon: "ti-clipboard-list", cls: "si-primary"  },
          { label: "Approved",         value: totalApproved, icon: "ti-circle-check",   cls: "si-success"  },
          { label: "Pending Approval", value: totalPending,  icon: "ti-clock",          cls: "si-warn"     },
          { label: "Rejected",         value: stats?.rejected ?? 0, icon: "ti-x-circle", cls: "si-error"   },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
              <div>
                <div className="stat-label">{s.label}</div>
                <div className="stat-value">{s.value}</div>
                <div className="stat-sub">This year ({currentYear})</div>
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

      {/* Leave type distribution */}
      {balances.length === 0 && (
        <div className="card" style={{ padding: "40px 20px", textAlign: "center" }}>
          <i className="ti ti-chart-bar-off" style={{ fontSize: 32, color: "var(--outline-v)", display: "block", marginBottom: 8 }} />
          <p style={{ color: "var(--on-variant)", fontSize: 13 }}>
            No leave balance data for {currentYear}. HR can credit balances from Leave Settings.
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
