"use client";

// Workforce dashboard — pixel-for-pixel replication of the reference
// mockup's layout, spacing and copy. The KPI row and "Dashboard overview"
// status panel pull real numbers from HRDashboardOverviewView
// (apps/dashboard/views/overview.py) via useDashboardOverview — the
// mockup's own static "Interactive Demo Data" framing is kept as a literal
// label (badge) elsewhere, not as an excuse to fabricate the underlying
// numbers. No capability-hub section on this page — the reference's exact
// site map shows one only on Organization/Attendance/Leave/Payroll/Reports/
// Settings, not Dashboard or Performance.

import { useRouter } from "next/navigation";
import type { SessionPayload } from "@/lib/session";
import { useDashboardOverview } from "@/hooks/useDashboardOverview";
import { StatCard } from "@/components/dashboard/StatCard";
import OverviewList from "@/components/dashboard/OverviewList";
import QuickActionsGrid from "@/components/dashboard/QuickActionsGrid";

interface Props { session: SessionPayload }

export default function HRDashboard({ session }: Props) {
  void session;
  const router = useRouter();
  const { data } = useDashboardOverview();

  return (
    <div>
      <div className="pagehead">
        <div>
          <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>Dashboard / Overview</div>
          <h1>Workforce <em>dashboard</em></h1>
          <p className="lede">
            A live view of people operations, payroll readiness and work requiring attention.
          </p>
        </div>
        <button className="btn btn-filled" onClick={() => router.push("/dashboard/approvals")}>
          Review alerts
        </button>
      </div>

      <div className="stats">
        <StatCard label="TOTAL HEADCOUNT" value={data?.total_headcount ?? "—"} sub={data ? `+${data.new_this_month} this month` : ""} tone="brand" />
        <StatCard label="PRESENT TODAY" value={data?.present_today ?? "—"} sub={data ? `${data.attendance_pct}% attendance` : ""} tone="ok" />
        <StatCard label="PAYROLL READY" value={data?.payroll_ready ?? "—"} sub={data ? `${data.payroll_blocked} records blocked` : ""} tone="warn" />
        <StatCard label="OPEN REQUESTS" value={data?.open_requests ?? "—"} sub={data ? "awaiting you" : ""} tone="crit" />
      </div>

      <div className="module-grid">
        <OverviewList
          title="Dashboard overview"
          emptyIcon="ti-layout-dashboard"
          items={[
            {
              label: "Payroll readiness", sub: new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" }),
              chip: data ? `${data.payroll_ready} of ${data.payroll_total} ready` : "—", chipTone: "warn",
              onOpen: () => router.push("/dashboard/payroll"),
            },
            {
              label: "Onboarding", sub: "Employees still onboarding",
              chip: data ? `${data.onboarding_in_progress} in progress` : "—", chipTone: "warn",
              onOpen: () => router.push("/dashboard/employees"),
            },
            {
              label: "Attendance", sub: "Today · all locations",
              chip: data ? `${data.attendance_exceptions_today} exceptions` : "—", chipTone: "error",
              onOpen: () => router.push("/dashboard/attendance"),
            },
            {
              label: "Compliance", sub: "Required document uploads",
              chip: data ? `${data.compliance_pct}% complete` : "—", chipTone: "success",
              onOpen: () => router.push("/dashboard/settings/audit"),
            },
          ]}
        />

        <QuickActionsGrid
          items={[
            { title: "Hire an employee", sub: "Start the guided onboarding flow", onClick: () => router.push("/dashboard/employees") },
            { title: "Review leave", sub: "Requests need a decision", onClick: () => router.push("/dashboard/leave") },
            { title: "Run payroll checks", sub: "Resolve blocked records", onClick: () => router.push("/dashboard/payroll") },
            { title: "Export workforce report", sub: "Download the current snapshot", onClick: () => router.push("/dashboard/reports") },
          ]}
          chartData={data?.weekly_attendance ?? []}
        />
      </div>
    </div>
  );
}
