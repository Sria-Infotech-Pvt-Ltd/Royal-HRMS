"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { DashboardKPIs } from "@/types/dashboard";

interface Props { firstName: string }

export default function KpiConsole({ firstName }: Props) {
  const { data: kpis, loading } = useFetch<DashboardKPIs>(API.dashboard.kpis);

  const stats = [
    { icon: "ti-users",     val: loading ? "—" : String(kpis?.total_employees      ?? 0), lbl: "Total Employees",   sub: "Active headcount"     },
    { icon: "ti-checks",    val: loading ? "—" : String(kpis?.pending_approvals     ?? 0), lbl: "Pending Approvals", sub: "Across all modules"   },
    { icon: "ti-user-plus", val: loading ? "—" : String(kpis?.employees_onboarding ?? 0), lbl: "In Onboarding",     sub: "Step 2–4 in progress" },
    { icon: "ti-building",  val: loading ? "—" : String(kpis?.active_branches       ?? 0), lbl: "Active Branches",   sub: "All operational"      },
  ];

  return (
    <div
      className="mb-20"
      style={{
        background: "linear-gradient(135deg, #1a3a6e 0%, #0e2447 100%)",
        borderRadius: 10,
        overflow: "hidden",
        position: "relative",
      }}
    >
      <div style={{ position: "absolute", top: -50, right: -50, width: 180, height: 180, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.06)", pointerEvents: "none" }} />
      <div style={{ position: "absolute", top: -20, right: -20, width: 110, height: 110, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.04)", pointerEvents: "none" }} />

      {/* Top bar */}
      <div style={{ display: "flex", alignItems: "center", padding: "10px 16px 0", position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 6, background: "rgba(255,255,255,0.10)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: "#fff", flexShrink: 0 }}>
            <i className="ti ti-terminal-2" />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "rgba(255,255,255,0.5)", textTransform: "uppercase", lineHeight: 1 }}>System Console</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#fff", lineHeight: 1.2 }}>Welcome back, {firstName}</div>
          </div>
        </div>
      </div>

      <div style={{ margin: "6px 16px 0", borderBottom: "1px solid rgba(255,255,255,0.08)" }} />

      {/* Stats */}
      <div className="stats-grid">
        {stats.map(stat => (
          <div key={stat.lbl} style={{ padding: "8px 14px", display: "flex", flexDirection: "column", gap: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <i className={`ti ${stat.icon}`} style={{ fontSize: 12, color: "rgba(255,255,255,0.4)" }} />
              <span style={{ fontSize: 18, fontWeight: 800, color: "#fff", lineHeight: 1 }}>{stat.val}</span>
            </div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.72)" }}>{stat.lbl}</div>
            <div style={{ fontSize: 10, color: "rgba(255,255,255,0.36)" }}>{stat.sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
