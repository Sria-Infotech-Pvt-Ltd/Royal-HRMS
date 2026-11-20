"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import type { DashboardData, PaginatedCorrections } from "@/types/attendance";
import AttendanceTab     from "./AttendanceTab";
import AttendanceSummaryStrip from "./AttendanceSummaryStrip";
import AttendancePageTabs, { type AttendanceTabItem } from "./AttendancePageTabs";
import OtEntryTab        from "./OtEntryTab";
import InvalidPunchesTab from "./InvalidPunchesTab";
import UnpunchesTab      from "./UnpunchesTab";
import CorrectionsTab    from "./CorrectionsTab";
import EmployeeMonthView from "./EmployeeMonthView";
import WeeklyOffAssignmentTab from "./WeeklyOffAssignmentTab";
import { buildAttendanceSearch, parseAttendanceLocation, type AttendanceTabId } from "./attendanceTabs";
import { useAfterMount } from "@/hooks/useAfterMount";
import { useT } from "@/hooks/useI18n";

type TabId = AttendanceTabId;

function todayLabel(): string {
  return new Date().toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

export default function AttendanceDetailClient({ initialTab, onBack }: { initialTab?: string; onBack?: () => void }) {
  const t = useT();
  const today = useAfterMount(todayLabel, "");  // the viewer's own date, after mount: the server's clock may differ
  const [active, setActive]       = useState<TabId>(() => parseAttendanceLocation(initialTab ? `?tab=${initialTab}` : "").tab);
  const [viewMode, setViewMode]   = useState<"team" | "employee">("team");
  const [preEmployee, setPreEmployee] = useState<string | null>(null);
  const [preMonth, setPreMonth]   = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");

  // One click from a KPI card straight to the matching filtered rows below —
  // switches to the Attendance tab's Team Day View (where the status filter
  // applies) and sets the filter, instead of making the user land on the tab
  // and then hunt for the right chip themselves.
  function jumpToStatus(status: string) {
    goTo("attendance", "team");
    setStatusFilter(status);
  }

  // The URL is the source of truth for tab and view: read it on load and on browser back/forward, write it on every change.
  useEffect(() => {
    function syncFromUrl() {
      const params = new URLSearchParams(window.location.search);
      const location = parseAttendanceLocation(window.location.search);
      if (params.has("tab") || !initialTab) setActive(location.tab);
      setViewMode(location.view);
      if (params.get("employee")) setPreEmployee(params.get("employee"));
      if (params.get("month")) setPreMonth(params.get("month"));
    }
    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, [initialTab]);

  function goTo(tab: TabId, view: "team" | "employee") {
    setActive(tab);
    setViewMode(view);
    const search = buildAttendanceSearch(window.location.search, { tab, view });
    window.history.pushState(null, "", `${window.location.pathname}${search}`);
  }

  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);

  const dashboardUrl = user
    ? `${API.attendance.dashboard}${effectiveBranch ? `?branch=${encodeURIComponent(effectiveBranch)}` : ""}`
    : null;
  const { data: dashboard, error: dashboardError, status: dashboardStatus, refetch: refetchDashboard } = useFetch<DashboardData>(dashboardUrl);

  // Pending counts come from the caller's own review queue (the dashboard stats are cached per branch, not per user).
  const pendingUrl = user ? `${API.attendance.corrections}?status=pending&page_size=1` : null;
  const hrPendingUrl = user ? `${API.attendance.corrections}?status=l2_pending&page_size=1` : null;
  const { data: pendingData } = useFetch<PaginatedCorrections>(pendingUrl);
  const { data: hrPendingData } = useFetch<PaginatedCorrections>(hrPendingUrl);
  const pendingCorrections = (pendingData?.count ?? 0) + (hrPendingData?.count ?? 0);

  const cards    = dashboard?.stat_cards;

  const TABS: (AttendanceTabItem & { id: TabId })[] = [
    { id: "attendance", label: "Attendance", icon: "ti-calendar-stats" },
    { id: "ot", label: "OT Entry", icon: "ti-clock-plus" },
    { id: "invalid", label: "Invalid Punches", icon: "ti-alert-triangle", badge: dashboard?.tab_badges.invalid_punches },
    { id: "unpunches", label: "Un-punches", icon: "ti-clock-off", badge: dashboard?.tab_badges.un_punches },
    { id: "corrections", label: "Corrections", icon: "ti-file-description", badge: pendingCorrections },
    { id: "weekly-off", label: "Weekly Off Assignment", icon: "ti-moon" },
  ];

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-title">
            {t("Attendance & Time")}{!unrestricted && effectiveBranch ? ` — ${effectiveBranch}` : ""}
          </div>
          <div className="page-sub">{t("Monitor daily attendance, overtime, and correction requests")}</div>
        </div>
        <div className="page-actions">
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{today}</span>
          {onBack && (
            <button className="btn btn-ghost" onClick={onBack}>
              <i className="ti ti-arrow-left" /> {t("Back to overview")}
            </button>
          )}
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

      {/* Today at a glance: one slim strip; each number jumps to the matching rows */}
      <AttendanceSummaryStrip cards={cards} onJump={jumpToStatus} failure={dashboardError ? { status: dashboardStatus, onRetry: refetchDashboard } : null} />

      {/* Tab bar */}
      <AttendancePageTabs
        tabs={TABS} active={active}
        onSelect={id => goTo(id as TabId, id === "attendance" ? viewMode : "team")}
      />

      {/* Tab content */}
      <div>
        {active === "attendance" && (
          <>
            {/* View mode toggle */}
            <div style={{ display: "flex", gap: 6, marginBottom: 18, padding: "10px 0 0" }}>
              <button
                className={viewMode === "team" ? "btn btn-filled btn-sm" : "btn btn-ghost btn-sm"}
                onClick={() => goTo("attendance", "team")}
                style={{ gap: 6 }}
              >
                <i className="ti ti-layout-list" /> {t("Team Day View")}
              </button>
              <button
                className={viewMode === "employee" ? "btn btn-filled btn-sm" : "btn btn-ghost btn-sm"}
                onClick={() => goTo("attendance", "employee")}
                style={{ gap: 6 }}
              >
                <i className="ti ti-calendar-user" /> {t("Employee Month View")}
              </button>
            </div>
            {viewMode === "team"
              ? <AttendanceTab key="team-day" onMutated={refetchDashboard} status={statusFilter} onStatusChange={setStatusFilter} />
              : <EmployeeMonthView key="employee-month" initialEmployee={preEmployee} initialMonth={preMonth} />
            }
          </>
        )}
        {active === "ot"         && <OtEntryTab key="ot" />}
        {active === "invalid"    && <InvalidPunchesTab onMutated={refetchDashboard} />}
        {active === "unpunches"  && <UnpunchesTab key="unpunches" />}
        {active === "corrections" && <CorrectionsTab key="corrections" />}
        {active === "weekly-off" && <WeeklyOffAssignmentTab key="weekly-off" />}
      </div>
    </div>
  );
}
