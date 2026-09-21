"use client";

import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import {
  KpiTile, OverviewRow, QuickActionTile, WeeklyBarChart, BrandBanner,
  CapabilityGrid, OperationalToolsGrid, PlatformSafeguards,
} from "@/components/dashboard/ModuleOverviewKit";

interface OverviewRowData { name: string; context: string; status_label: string; status_kind: "success" | "error" | "warn"; link: string }
interface OverviewData {
  pending: number; on_leave_today: number; upcoming: number; holidays_remaining: number;
  holiday_states: string[];
  overview_rows: OverviewRowData[]; weekly_chart: { label: string; count: number }[];
}

const CAPABILITIES = [
  { title: "Policy engine", desc: "Accrual, carry-forward, expiry, encashment and negative balance rules.", href: "/dashboard/settings/leave-policy" },
  { title: "Request workflow", desc: "Employee request, coverage check, manager approval and HR override.", href: "/dashboard/approvals" },
  { title: "Leave year", desc: "Multiple calendars by entity, location and employee group.", href: "/dashboard/settings/leave-policy" },
  { title: "Eligibility", desc: "Proration for joiners, exits, probation and contract types.", href: "/dashboard/settings/leave-policy" },
  { title: "Coverage planning", desc: "Team calendar, overlap warnings and backup ownership.", href: "/dashboard/leave?tab=calendar" },
  { title: "Statutory leave", desc: "Maternity, paternity, adoption and location-specific categories.", href: "/dashboard/settings/leave-policy" },
  { title: "Adjustments", desc: "Audited grants, reversals, lapses and opening balances.", href: "/dashboard/leave" },
  { title: "Payroll handoff", desc: "Approved leave and loss-of-pay inputs sent to payroll.", href: "/dashboard/payroll" },
];

const OPERATIONAL_TOOLS = [
  { title: "New request", desc: "Submit leave with dates, reason and attachment.", href: "/dashboard/leave?tab=apply" },
  { title: "Approval queue", desc: "Approve, reject or return requests.", href: "/dashboard/approvals" },
  { title: "Balance adjustment", desc: "Post an audited credit or debit.", href: "/dashboard/leave" },
  { title: "Team calendar", desc: "Review coverage and overlapping absences.", href: "/dashboard/leave?tab=calendar" },
  { title: "Year-end process", desc: "Carry forward, encash or lapse balances.", href: "/dashboard/settings/leave-policy" },
  { title: "Policy simulator", desc: "Preview entitlement for an employee and date.", href: "/dashboard/settings/leave-policy" },
];

export default function LeaveOverviewClient({ onOpen }: { onOpen: (tab?: string) => void }) {
  const router = useRouter();
  const { data } = useFetch<OverviewData>(API.dashboard.leaveOverview);

  function go(href: string) {
    if (href.startsWith("/dashboard/leave")) {
      const tab = new URL(href, "http://x").searchParams.get("tab") ?? undefined;
      onOpen(tab);
    } else {
      router.push(href);
    }
  }

  return (
    <div>
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>Dashboard / Time / Leave</div>
      <div className="pagehead">
        <div>
          <h1>Leave <em>management</em></h1>
          <p className="lede">
            Review requests, balances, holiday calendars and coverage before approving time away.
          </p>
        </div>
        <button className="btn btn-filled" onClick={() => onOpen("apply")}>New leave request</button>
      </div>

      <div className="stats">
        <KpiTile label="PENDING" value={data?.pending ?? "—"} sub="Awaiting approval" tone="warn" />
        <KpiTile label="ON LEAVE TODAY" value={data?.on_leave_today ?? "—"} sub="Coverage confirmed" tone="brand" />
        <KpiTile label="UPCOMING" value={data?.upcoming ?? "—"} sub="Next 14 days" tone="ok" />
        <KpiTile label="HOLIDAYS" value={data?.holidays_remaining ?? "—"} sub="Remaining this year" tone="brand" />
      </div>

      <div className="module-grid">
        <div className="module-card">
          <div className="mc-head">
            <div className="mc-title">Leave overview</div>
            <div className="mc-sub">Current records and items requiring attention.</div>
          </div>
          <div style={{ padding: "0 20px 4px" }}>
            {!data || data.overview_rows.length === 0 ? (
              <div className="empty-state"><i className="ti ti-calendar-off" /><h3>No requests yet</h3></div>
            ) : data.overview_rows.map((row, i) => (
              <OverviewRow key={i} label={row.name} sub={row.context} chip={row.status_label} chipTone={row.status_kind} onOpen={() => go(row.link)} />
            ))}
          </div>
        </div>

        <div className="module-card">
          <div className="mc-head">
            <div className="mc-title">Quick actions</div>
            <div className="mc-sub">Common tasks for your current role.</div>
          </div>
          <div className="quick-grid">
            <QuickActionTile title="Leave balances" sub="Review employee entitlements" onClick={() => onOpen()} />
            <QuickActionTile title="Approval queue" sub={data ? `${data.pending} requests waiting` : ""} onClick={() => router.push("/dashboard/approvals")} />
            <QuickActionTile title="Holiday calendar" sub={data && data.holiday_states.length > 0 ? data.holiday_states.join(" · ") : "No locations configured"} onClick={() => router.push("/dashboard/settings/holiday-calendar")} />
            <QuickActionTile title="Leave policies" sub="Casual · Sick · Earned" onClick={() => router.push("/dashboard/settings/leave-policy")} />
          </div>
          <WeeklyBarChart data={data?.weekly_chart ?? []} />
        </div>
      </div>

      <BrandBanner />
      <CapabilityGrid title="Complete capability coverage" sub="Lifecycle functions designed for multi-year HR operations." items={CAPABILITIES} onOpen={go} />
      <OperationalToolsGrid title="Operational tools" sub="Role-aware tools with effective dates, approval states and audit events." items={OPERATIONAL_TOOLS} onLaunch={go} />
      <PlatformSafeguards />
    </div>
  );
}
