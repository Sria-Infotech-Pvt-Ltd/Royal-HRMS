"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import type { DashboardData } from "@/types/attendance";
import AttendanceTab     from "./_components/AttendanceTab";
import OtEntryTab        from "./_components/OtEntryTab";
import InvalidPunchesTab from "./_components/InvalidPunchesTab";
import UnpunchesTab      from "./_components/UnpunchesTab";

type TabId = "attendance" | "ot" | "invalid" | "unpunches";

interface Tab {
  id: TabId;
  label: string;
  badge?: number;
}

const TODAY_LABEL = new Date().toLocaleDateString("en-IN", {
  weekday: "short", day: "numeric", month: "short", year: "numeric",
});

export default function AttendancePage() {
  const [active, setActive] = useState<TabId>("attendance");
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);

  const dashboardUrl = user
    ? `${API.attendance.dashboard}${effectiveBranch ? `?branch=${encodeURIComponent(effectiveBranch)}` : ""}`
    : null;
  const { data: dashboard, refetch: refetchDashboard } = useFetch<DashboardData>(dashboardUrl);

  const cards    = dashboard?.stat_cards;
  const total    = cards?.total_employees ?? 0;
  const pct = (value: number | undefined) => (total > 0 && value !== undefined ? Math.round((value / total) * 100) : 0);

  const TABS: Tab[] = [
    { id: "attendance", label: "Attendance"      },
    { id: "ot",         label: "OT Entry"        },
    { id: "invalid",    label: "Invalid Punches", badge: dashboard?.tab_badges.invalid_punches },
    { id: "unpunches",  label: "Un-punches",      badge: dashboard?.tab_badges.un_punches },
  ];

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-title">
            Attendance &amp; Time{!unrestricted && effectiveBranch ? ` — ${effectiveBranch}` : ""}
          </div>
          <div className="page-sub">Monitor daily attendance, overtime, and correction requests</div>
        </div>
        <div className="page-actions">
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{TODAY_LABEL}</span>
        </div>
      </div>

      {!unrestricted && effectiveBranch && (
        <div
          style={{
            display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 12px",
            background: "var(--info-c)", color: "var(--info)", borderRadius: 6,
            fontSize: 12, marginBottom: 16,
          }}
        >
          🏢 Viewing data for {effectiveBranch} only
        </div>
      )}

      {/* Summary stat cards */}
      <div className="stats-grid mb-24">
        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Present Today</div>
              <div className="stat-value" style={{ color: "var(--success)" }}>{cards?.present_today ?? "—"}</div>
              <div className="stat-sub">of {total} employees</div>
            </div>
            <div className="stat-icon si-success"><i className="ti ti-user-check" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${pct(cards?.present_today)}%`, background: "var(--success)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Absent</div>
              <div className="stat-value" style={{ color: "var(--error)" }}>{cards?.absent ?? "—"}</div>
              <div className="stat-sub">No check-in recorded</div>
            </div>
            <div className="stat-icon si-error"><i className="ti ti-user-off" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${pct(cards?.absent)}%`, background: "var(--error)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Late Arrivals</div>
              <div className="stat-value" style={{ color: "var(--warn)" }}>{cards?.late_arrivals ?? "—"}</div>
              <div className="stat-sub">Arrived after 09:15</div>
            </div>
            <div className="stat-icon si-warn"><i className="ti ti-clock-exclamation" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${pct(cards?.late_arrivals)}%`, background: "var(--warn)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">On Leave</div>
              <div className="stat-value" style={{ color: "var(--info)" }}>{cards?.on_leave ?? "—"}</div>
              <div className="stat-sub">Approved leave</div>
            </div>
            <div className="stat-icon si-info"><i className="ti ti-calendar-event" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${pct(cards?.on_leave)}%`, background: "var(--info)" }} />
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab${active === tab.id ? " active" : ""}`}
            onClick={() => setActive(tab.id)}
          >
            {tab.label}
            {!!tab.badge && (
              <span style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                minWidth: 18, height: 18, borderRadius: 9, background: "var(--error)",
                color: "#fff", fontSize: 10, fontWeight: 700, marginLeft: 6, padding: "0 4px",
              }}>
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {active === "attendance" && <AttendanceTab onMutated={refetchDashboard} />}
        {active === "ot"         && <OtEntryTab />}
        {active === "invalid"    && <InvalidPunchesTab onMutated={refetchDashboard} />}
        {active === "unpunches"  && <UnpunchesTab />}
      </div>
    </div>
  );
}
