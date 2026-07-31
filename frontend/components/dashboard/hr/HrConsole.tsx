"use client";

import { useEffect, useState } from "react";
import ClockInButton from "@/components/ClockInButton";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { HRKPIs, LeaveUpdatePayload } from "@/types/dashboard";

interface Props { firstName: string }

export default function HrConsole({ firstName }: Props) {
  const { data: kpis, loading, refetch } = useFetch<HRKPIs>(API.dashboard.hrKpis);
  // Live pending_actions count pushed by the backend over WebSocket.
  const [livePendingActions, setLivePendingActions] = useState<number | null>(null);

  useEffect(() => {
    function handleAttendanceUpdate() { refetch(); }
    window.addEventListener("attendance:updated", handleAttendanceUpdate);
    return () => window.removeEventListener("attendance:updated", handleAttendanceUpdate);
  }, [refetch]);

  useEffect(() => {
    function handleLeaveUpdate(event: Event) {
      const { detail } = event as CustomEvent<LeaveUpdatePayload>;
      if (detail?.pending_actions !== null && detail?.pending_actions !== undefined) {
        setLivePendingActions(detail.pending_actions);
      }
    }
    window.addEventListener("leave:updated", handleLeaveUpdate);
    return () => window.removeEventListener("leave:updated", handleLeaveUpdate);
  }, []);

  const today = new Date().toLocaleDateString("en-IN", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  const stats = [
    { icon: "ti-users",      val: loading ? "—" : String(kpis?.total_workforce               ?? 0), lbl: "Total Workforce",     sub: "Active employees"   },
    { icon: "ti-checks",     val: loading ? "—" : String(livePendingActions ?? kpis?.pending_actions ?? 0), lbl: "Pending Actions",     sub: "Awaiting review"    },
    { icon: "ti-video",      val: loading ? "—" : String(kpis?.active_interviews              ?? 0), lbl: "Active Interviews",   sub: "In pipeline"        },
    { icon: "ti-calendar-x", val: loading ? "—" : String(kpis?.attendance_correction_pending ?? 0), lbl: "Corrections Pending", sub: "Needs attention"    },
  ];

  const isClockedIn = kpis?.clocked_in;

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
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 16px 0", position: "relative", flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 6, background: "rgba(255,255,255,0.10)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: "#fff", flexShrink: 0 }}>
            <i className="ti ti-users-group" />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "rgba(255,255,255,0.5)", textTransform: "uppercase", lineHeight: 1 }}>HR Operations</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#fff", lineHeight: 1.2 }}>Welcome back, {firstName}</div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }} suppressHydrationWarning>{today}</span>
          {!loading && kpis && (
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 700,
              padding: "3px 10px", borderRadius: 20,
              background: isClockedIn ? "rgba(22,163,74,0.25)" : "rgba(220,38,38,0.20)",
              color: isClockedIn ? "#4ade80" : "#f87171",
              border: `1px solid ${isClockedIn ? "rgba(74,222,128,0.3)" : "rgba(248,113,113,0.3)"}`,
            }}>
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: isClockedIn ? "#4ade80" : "#f87171", flexShrink: 0 }} />
              {isClockedIn ? "Clocked In" : "Not Clocked In"}
            </span>
          )}
          <ClockInButton onPunchSuccess={refetch} />
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
