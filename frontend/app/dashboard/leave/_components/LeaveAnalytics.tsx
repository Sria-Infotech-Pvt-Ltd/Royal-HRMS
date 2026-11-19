"use client";

import type { CSSProperties } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { getLeaveYear } from "@/lib/fiscalYear";
import { usePermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { LeaveStats, LEAVE_TYPE_CONFIG } from "../_data";
import { LeaveStyles } from "./leaveStyles";
import { MonthlyBars, StatusDonut } from "./LeaveCharts";
import { tr } from "@/lib/i18n/tr";

export default function LeaveAnalytics() {
  const canApproveLeave = usePermission("leave.approve");
  const currentUser     = useCurrentUser();
  // Own-vs-team/branch/org scope is a permission decision, not a role-name
  // one — mirrors the same fix in LeaveDashboard.tsx.
  const isEmployee  = !canApproveLeave && !currentUser?.can_manage_team && !currentUser?.can_manage_branch;
  const currentYear = getLeaveYear();
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
  const lopRequests   = stats?.lop_requests ?? 0;
  const summary = [
    { label: tr("Total requests"),   value: totalAll,             icon: "ti-clipboard-list", accent: "var(--brand)", sub: tr("This year ({currentYear})", { currentYear: currentYear }) },
    { label: tr("Approved"),         value: totalApproved,        icon: "ti-circle-check",   accent: "#16a34a", sub: tr("This year ({currentYear})", { currentYear: currentYear }) },
    { label: tr("Pending approval"), value: totalPending,         icon: "ti-clock",          accent: "#d97706", sub: tr("This year ({currentYear})", { currentYear: currentYear }) },
    { label: tr("Rejected"),         value: stats?.rejected ?? 0, icon: "ti-circle-x",       accent: "#dc2626", sub: tr("This year ({currentYear})", { currentYear: currentYear }) },
    { label: tr("Loss of pay"),      value: stats?.lop_days ?? 0, icon: "ti-coin-off",       accent: "#ea580c", sub: tr(lopRequests === 1 ? "{count} request in {year}" : "{count} requests in {year}", { count: lopRequests, year: currentYear }) },
  ];
  const statusRows = [
    { label: tr("Approved"),  value: totalApproved,         color: "#16a34a" },
    { label: tr("Pending"),   value: totalPending,          color: "#d97706" },
    { label: tr("Rejected"),  value: stats?.rejected  ?? 0, color: "#dc2626" },
    { label: tr("Cancelled"), value: stats?.cancelled ?? 0, color: "#9ca3af" },
  ];
  const byType = stats?.by_type ?? [];
  // 12 empty months when the server has nothing yet, so the chart axes still draw.
  const monthly = stats?.monthly ?? Array.from({ length: 12 }, (_, index) => ({ month: index + 1, requests: 0, approved_days: 0 }));
  const topTypeDays = Math.max(...byType.map(row => row.days), 1);
  const percentOf = (value: number) => (totalAll > 0 ? Math.round((value / totalAll) * 100) : 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <LeaveStyles />

      {/* Numbers stay as one slim strip; the charts below are the analytics. */}
      <div className="lv-strip">
        {summary.map(item => (
          <span key={item.label} className="lv-chip" title={item.sub} style={{ "--lv-accent": item.accent } as CSSProperties}>
            <i className={`ti ${item.icon}`} /> {item.label}: <b>{item.value}</b>
          </span>
        ))}
      </div>

      <div className="lv-panel">
        <div className="lv-panel-head">
          <span><i className="ti ti-chart-bar" /> {tr("Month by month")} · {currentYear}</span>
          <div className="lv-legend">
            <span><i style={{ background: "var(--brand)", opacity: 0.35 }} />{tr("Requests")}</span>
            <span><i style={{ background: "#16a34a" }} />{tr("Approved days")}</span>
          </div>
        </div>
        <div className="lv-panel-body" style={{ color: "var(--on-variant)" }}>
          <MonthlyBars data={monthly} />
          {totalAll === 0 && <div className="lv-empty" style={{ padding: "6px 0 0" }}>{tr("No leave requests in {year} yet. The chart fills in as requests are made.", { year: currentYear })}</div>}
        </div>
      </div>

      <div className="lv-panel">
        <div className="lv-panel-head"><span><i className="ti ti-chart-pie" /> {tr("Approved days by leave type")}</span></div>
        <div className="lv-panel-body">
          {byType.length === 0 && <div className="lv-empty" style={{ padding: "10px 0" }}>{tr("No approved leave in {year} yet.", { year: currentYear })}</div>}
          {byType.map(row => (
              <div key={row.leave_type} className="lv-meter">
                <div className="lv-meter-head"><b>{LEAVE_TYPE_CONFIG[row.leave_type]?.label ?? row.leave_type}</b><span><b>{row.days}</b> {tr(row.days === 1 ? "day" : "days")}</span></div>
                <div className="lv-bar" style={{ marginTop: 0, "--lv-accent": LEAVE_TYPE_CONFIG[row.leave_type]?.color ?? "var(--primary)" } as CSSProperties}><i style={{ width: `${(row.days / topTypeDays) * 100}%` }} /></div>
              </div>
          ))}
        </div>
      </div>

      <div className="lv-split">
        {balances.length > 0 && (
          <div className="lv-panel">
            <div className="lv-panel-head"><span><i className="ti ti-chart-bar" /> {tr("Leave balance breakdown")}</span></div>
            <div className="lv-panel-body">
              {balances.map(b => {
                const percentUsed = b.total_days > 0 ? Math.min(100, Math.round((b.used_days / b.total_days) * 100)) : 0;
                const color = LEAVE_TYPE_CONFIG[b.leave_type]?.color ?? "var(--primary)";
                return (
                  <div key={b.leave_type} className="lv-meter">
                    <div className="lv-meter-head">
                      <b>{b.leave_type_display}</b>
                      <span>{tr("{used} used of {total}", { used: b.used_days, total: b.total_days })} · <b>{tr("{count} left", { count: b.available })}</b></span>
                    </div>
                    <div className="lv-bar" style={{ marginTop: 0, "--lv-accent": color } as CSSProperties}><i style={{ width: `${percentUsed}%` }} /></div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Approvers never receive balance rows, so the empty note is for employees only. */}
        {isEmployee && balances.length === 0 && (
          <div className="lv-panel">
            <div className="lv-empty"><i className="ti ti-chart-bar-off" />{tr("No leave balance data for {year}. Contact HR to credit your annual leave.", { year: currentYear })}</div>
          </div>
        )}

        {(
          <div className="lv-panel">
            <div className="lv-panel-head"><span><i className="ti ti-chart-donut" /> {tr("Request status")}</span></div>
            <div className="lv-panel-body" style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap", color: "var(--on-bg)" }}>
              <StatusDonut slices={statusRows} total={totalAll} />
              <div style={{ flex: 1, minWidth: 160 }}>
                {statusRows.map(row => (
                  <div key={row.label} className="lv-meter-head" style={{ marginBottom: 8 }}>
                    <span><span className="lv-dot" style={{ display: "inline-block", width: 9, height: 9, marginRight: 8, boxShadow: "none", "--lv-accent": row.color } as CSSProperties} />{row.label}</span>
                    <span><b>{row.value}</b> ({percentOf(row.value)}%)</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
