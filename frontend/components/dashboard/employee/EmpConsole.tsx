"use client";

import { useEffect } from "react";
import ClockInButton from "@/components/ClockInButton";
import { useEmployeeKPIs, useAttendanceStatus } from "@/hooks/useEmployeeDashboard";

const ATTENDANCE_LABEL: Record<string, string> = {
  present:    "Present",
  late:       "Late",
  absent:     "Absent",
  on_leave:   "On Leave",
  weekly_off: "Weekly Off",
  holiday:    "Holiday",
  half_day:   "Half Day",
  incomplete: "Incomplete",
};

const ATTENDANCE_COLOR: Record<string, { color: string; bg: string }> = {
  present:    { color: "#16a34a", bg: "rgba(22,163,74,0.20)"   },
  late:       { color: "#d97706", bg: "rgba(217,119,6,0.20)"   },
  absent:     { color: "#dc2626", bg: "rgba(220,38,38,0.18)"   },
  on_leave:   { color: "#2563eb", bg: "rgba(37,99,235,0.18)"   },
  weekly_off: { color: "#94a3b8", bg: "rgba(148,163,184,0.18)" },
  holiday:    { color: "#7c3aed", bg: "rgba(124,58,237,0.18)"  },
  half_day:   { color: "#d97706", bg: "rgba(217,119,6,0.18)"   },
  incomplete: { color: "#dc2626", bg: "rgba(220,38,38,0.15)"   },
};

interface Props { firstName: string }

export default function EmpConsole({ firstName }: Props) {
  const { data: kpis,   loading: kpiLoading,    status: kpiHttpStatus,    refetch: refetchKpis }   = useEmployeeKPIs();
  const { data: status, loading: statusLoading, status: statusHttpStatus, refetch: refetchStatus } = useAttendanceStatus();

  // Clocking in/out changes both of these, but each is fetched independently
  // on mount — without this, the "Late"/attendance badge and stats here keep
  // showing what they fetched at page-load until a full reload.
  function handlePunchSuccess() {
    refetchKpis();
    refetchStatus();
  }

  // Voice commands bypass the onPunchSuccess callback — listen to the WS event instead.
  useEffect(() => {
    window.addEventListener("attendance:updated", handlePunchSuccess);
    return () => window.removeEventListener("attendance:updated", handlePunchSuccess);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refetchKpis, refetchStatus]);

  const loading = kpiLoading || statusLoading;
  // Both endpoints are gated behind the same onboarding/assessment check —
  // if either 403'd, the 0s below aren't real data, they're a locked widget.
  const isLocked = kpiHttpStatus === 403 || statusHttpStatus === 403;
  const attendanceKey = kpis?.today_attendance?.status?.toLowerCase() ?? "";
  const attendanceInfo = ATTENDANCE_COLOR[attendanceKey] ?? { color: "rgba(255,255,255,0.5)", bg: "rgba(255,255,255,0.10)" };

  const showDash = loading || isLocked;
  const stats = [
    {
      icon: "ti-fingerprint",
      val:  showDash ? "—" : `${kpis?.days_present ?? 0} / ${kpis?.working_days ?? 0}`,
      lbl:  "Days Present",
      sub:  "This month",
    },
    {
      icon: "ti-calendar-x",
      val:  showDash ? "—" : String(kpis?.absent_days ?? 0),
      lbl:  "Absent Days",
      sub:  "This month",
    },
    {
      icon: "ti-clipboard-list",
      val:  showDash ? "—" : String(kpis?.pending_action_items ?? 0),
      lbl:  "Action Items",
      sub:  "Require attention",
    },
    {
      icon: "ti-receipt",
      val:  showDash ? "—" : String(kpis?.pending_expense_claims ?? 0),
      lbl:  "Expense Claims",
      sub:  "Pending",
    },
  ];

  return (
    <div
      className="mb-20"
      style={{ background: "linear-gradient(135deg, #1a3a6e 0%, #0e2447 100%)", borderRadius: 10, overflow: "hidden", position: "relative" }}
    >
      <div style={{ position: "absolute", top: -50, right: -50, width: 180, height: 180, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.06)", pointerEvents: "none" }} />
      <div style={{ position: "absolute", top: -20, right: -20, width: 110, height: 110, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.04)", pointerEvents: "none" }} />

      {/* Top bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 16px 0", position: "relative", flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 6, background: "rgba(255,255,255,0.10)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: "#fff", flexShrink: 0 }}>
            <i className="ti ti-layout-dashboard" />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "rgba(255,255,255,0.5)", textTransform: "uppercase", lineHeight: 1 }}>My Workspace</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#fff", lineHeight: 1.2 }}>Welcome back, {firstName}</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {!loading && kpis?.today_attendance && (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 20, background: attendanceInfo.bg, color: attendanceInfo.color, border: `1px solid ${attendanceInfo.color}33` }}>
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: attendanceInfo.color, flexShrink: 0 }} />
              {ATTENDANCE_LABEL[attendanceKey] ?? attendanceKey}
            </span>
          )}
          <ClockInButton onPunchSuccess={handlePunchSuccess} />
        </div>
      </div>

      <div style={{ margin: "6px 16px 0", borderBottom: "1px solid rgba(255,255,255,0.08)" }} />

      {!loading && isLocked && (
        <div style={{ padding: "8px 16px 0", fontSize: 11, color: "rgba(255,255,255,0.7)", display: "flex", alignItems: "center", gap: 6 }}>
          <i className="ti ti-lock" style={{ fontSize: 12 }} />
          Complete your pending assessment to see your real stats —{" "}
          <a href="/onboarding/assessments" style={{ color: "#fff", fontWeight: 600, textDecoration: "underline" }}>go to Assessments</a>
        </div>
      )}

      {/* KPI stats */}
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

      {/* Attendance status strip */}
      {!loading && status && (
        <div style={{ display: "flex", alignItems: "center", gap: 20, padding: "7px 16px", borderTop: "1px solid rgba(255,255,255,0.08)", flexWrap: "wrap" }}>
          {[
            { icon: "ti-login",  label: "Clock In",  val: status.clock_in_time  ?? "—" },
            { icon: "ti-logout", label: "Clock Out", val: status.clock_out_time ?? "—" },
            { icon: "ti-clock",  label: "Working",   val: status.working_hours   || "—" },
          ].map(item => (
            <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
              <i className={`ti ${item.icon}`} style={{ color: "rgba(255,255,255,0.35)", fontSize: 12 }} />
              <span style={{ color: "rgba(255,255,255,0.45)" }}>{item.label}:</span>
              <span style={{ color: "#fff", fontWeight: 600 }}>{item.val}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
