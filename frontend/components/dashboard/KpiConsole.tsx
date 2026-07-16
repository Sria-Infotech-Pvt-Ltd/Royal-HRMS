"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { DashboardKPIs } from "@/types/dashboard";

interface Props { firstName: string }

function isHealthy(status: string | boolean | undefined): boolean {
  if (status === undefined || status === null) return false;
  if (typeof status === "boolean") return status;
  const s = String(status).toLowerCase();
  return s === "healthy" || s === "ok" || s === "true" || s === "up";
}

export default function KpiConsole({ firstName }: Props) {
  const { data: kpis, loading } = useFetch<DashboardKPIs>(API.dashboard.kpis);

  const health = [
    { label: "API",     ok: isHealthy(kpis?.api_status)      },
    { label: "DB",      ok: isHealthy(kpis?.database_status) },
    { label: "Mail",    ok: isHealthy(kpis?.mail_status)     },
    { label: "Storage", ok: isHealthy(kpis?.storage_status)  },
  ];

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
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 16px 0", position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 6, background: "rgba(255,255,255,0.10)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: "#fff", flexShrink: 0 }}>
            <i className="ti ti-terminal-2" />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "rgba(255,255,255,0.5)", textTransform: "uppercase", lineHeight: 1 }}>System Console</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#fff", lineHeight: 1.2 }}>Welcome back, {firstName}</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {health.map(s => (
            <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: "rgba(255,255,255,0.55)" }}>
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: s.ok ? "#4ade80" : "#f87171", flexShrink: 0 }} />
              {s.label}
            </div>
          ))}
        </div>
      </div>

      <div style={{ margin: "6px 16px 0", borderBottom: "1px solid rgba(255,255,255,0.08)" }} />

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)" }}>
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
