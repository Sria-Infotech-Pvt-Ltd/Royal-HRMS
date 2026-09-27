"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import type { DashboardData } from "@/types/attendance";
import AttendanceTab     from "./AttendanceTab";
import OtEntryTab        from "./OtEntryTab";
import InvalidPunchesTab from "./InvalidPunchesTab";
import UnpunchesTab      from "./UnpunchesTab";
import EmployeeMonthView from "./EmployeeMonthView";
import WeeklyOffAssignmentTab from "./WeeklyOffAssignmentTab";

type TabId = "attendance" | "ot" | "invalid" | "unpunches" | "weekly-off";

interface Tab {
  id: TabId;
  label: string;
  badge?: number;
}

const TODAY_LABEL = new Date().toLocaleDateString("en-IN", {
  weekday: "short", day: "numeric", month: "short", year: "numeric",
});

export default function AttendanceDetailClient({ initialTab, onBack }: { initialTab?: string; onBack?: () => void }) {
  const [active, setActive]       = useState<TabId>((initialTab as TabId) || "attendance");
  const [viewMode, setViewMode]   = useState<"team" | "employee">("team");
  const [preEmployee, setPreEmployee] = useState<string | null>(null);
  const [preMonth, setPreMonth]   = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");

  // One click from a KPI card straight to the matching filtered rows below —
  // switches to the Attendance tab's Team Day View (where the status filter
  // applies) and sets the filter, instead of making the user land on the tab
  // and then hunt for the right chip themselves.
  function jumpToStatus(status: string) {
    setActive("attendance");
    setViewMode("team");
    setStatusFilter(status);
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("view") === "employee") setViewMode("employee");
    if (params.get("employee")) setPreEmployee(params.get("employee"));
    if (params.get("month")) setPreMonth(params.get("month"));
  }, []);

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
    { id: "weekly-off", label: "Weekly Off Assignment" },
  ];

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          {onBack && (
            <button
              onClick={onBack}
              style={{ display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", color: "var(--primary)", fontSize: 12.5, fontWeight: 700, cursor: "pointer", padding: 0, marginBottom: 8 }}
            >
              <i className="ti ti-arrow-left" /> Back to overview
            </button>
          )}
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
        <button type="button" className="stat-card" style={{ cursor: "pointer", textAlign: "left" }} onClick={() => jumpToStatus("present")} title="View present employees">
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
        </button>

        <button type="button" className="stat-card" style={{ cursor: "pointer", textAlign: "left" }} onClick={() => jumpToStatus("absent")} title="View absent employees">
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
        </button>

        <button type="button" className="stat-card" style={{ cursor: "pointer", textAlign: "left" }} onClick={() => jumpToStatus("late")} title="View late arrivals">
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
        </button>

        <button type="button" className="stat-card" style={{ cursor: "pointer", textAlign: "left" }} onClick={() => jumpToStatus("on_leave")} title="View employees on leave">
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
        </button>
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
                minWidth: 18, height: 18, borderRadius: 9, background: "var(--error-solid)",
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
        {active === "attendance" && (
          <>
            {/* View mode toggle */}
            <div style={{ display: "flex", gap: 6, marginBottom: 18, padding: "10px 0 0" }}>
              <button
                className={viewMode === "team" ? "btn btn-filled btn-sm" : "btn btn-ghost btn-sm"}
                onClick={() => setViewMode("team")}
                style={{ gap: 6 }}
              >
                <i className="ti ti-layout-list" /> Team Day View
              </button>
              <button
                className={viewMode === "employee" ? "btn btn-filled btn-sm" : "btn btn-ghost btn-sm"}
                onClick={() => setViewMode("employee")}
                style={{ gap: 6 }}
              >
                <i className="ti ti-calendar-user" /> Employee Month View
              </button>
            </div>
            {viewMode === "team"
              ? <AttendanceTab onMutated={refetchDashboard} status={statusFilter} onStatusChange={setStatusFilter} />
              : <EmployeeMonthView initialEmployee={preEmployee} initialMonth={preMonth} />
            }
          </>
        )}
        {active === "ot"         && <OtEntryTab />}
        {active === "invalid"    && <InvalidPunchesTab onMutated={refetchDashboard} />}
        {active === "unpunches"  && <UnpunchesTab />}
        {active === "weekly-off" && <WeeklyOffAssignmentTab />}
      </div>
    </div>
  );
}
