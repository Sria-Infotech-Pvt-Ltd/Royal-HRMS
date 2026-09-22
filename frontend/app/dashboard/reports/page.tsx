"use client";

// Reports hub — a curated set of links to the reporting/analytics surfaces
// that already exist scattered across other modules (Audit Log, Leave
// Analytics, Attendance, Payroll), rather than a new reporting engine.

import { useRouter } from "next/navigation";
import { usePermission } from "@/hooks/usePermission";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import {
  KpiTile, OverviewRow, QuickActionTile, WeeklyBarChart,
} from "@/components/dashboard/ModuleOverviewKit";

const REPORT_ITEMS = [
  {
    id: "audit", route: "/dashboard/settings/audit", permission: "audit.view",
    icon: "ti-history", iconClass: "sc-system",
    label: "Audit Log", desc: "Every recorded action — views, edits, approvals and reveals.",
  },
  {
    id: "leave-analytics", route: "/dashboard/leave?tab=analytics", permission: "leave.view",
    icon: "ti-chart-bar", iconClass: "sc-modules",
    label: "Leave Analytics", desc: "Leave utilisation trends by type, department and branch.",
  },
  {
    id: "attendance", route: "/dashboard/attendance", permission: "attendance.create",
    icon: "ti-clock", iconClass: "sc-modules",
    label: "Attendance Overview", desc: "Presence, exceptions and regularization queue.",
  },
  {
    id: "payroll", route: "/dashboard/payroll", permission: "payroll.view",
    icon: "ti-report-money", iconClass: "sc-modules",
    label: "Payroll", desc: "Cycle readiness, salary revisions and statutory returns.",
  },
] as const;

interface OverviewRowData { name: string; context: string; status_label: string; status_kind: "success" | "error" | "warn"; link: string }
interface OverviewData {
  exports_today: number; audit_events_30d: number; weekly_chart: { label: string; count: number }[];
  overview_rows: OverviewRowData[];
}

export default function ReportsPage() {
  const router = useRouter();
  const canAudit     = usePermission("audit.view");
  const canLeave      = usePermission("leave.view");
  const canAttendance = usePermission("attendance.create");
  const canPayroll    = usePermission("payroll.view");
  const { data } = useFetch<OverviewData>(API.dashboard.reportsOverview);

  const has: Record<string, boolean> = {
    audit: canAudit, "leave-analytics": canLeave, attendance: canAttendance, payroll: canPayroll,
  };
  const visible = REPORT_ITEMS.filter(item => has[item.id]);

  return (
    <div>
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>Dashboard / Reports</div>
      <div className="pagehead">
        <div>
          <h1>People <em>reports</em></h1>
          <p className="lede">
            Run trusted workforce, attendance, payroll and compliance reports with role-aware access.
          </p>
        </div>
        <button className="btn btn-filled" onClick={() => router.push("/dashboard/employees")}>Build custom report</button>
      </div>

      <div className="stats">
        <KpiTile label="SAVED REPORTS" value={visible.length} sub="Available to you" tone="brand" />
        <KpiTile label="SCHEDULED" value="—" sub="Not yet configured" tone="warn" />
        <KpiTile label="EXPORTS TODAY" value={data?.exports_today ?? "—"} sub="Audit-tracked" tone="ok" />
        <KpiTile label="AUDIT EVENTS" value={data?.audit_events_30d ?? "—"} sub="Last 30 days" tone="brand" />
      </div>

      <div className="module-grid">
        <div className="module-card">
          <div className="mc-head">
            <div className="mc-title">Reports overview</div>
            <div className="mc-sub">Current records and items requiring attention.</div>
          </div>
          <div style={{ padding: "0 20px 4px" }}>
            {!data || data.overview_rows.length === 0 ? (
              <div className="empty-state"><i className="ti ti-chart-bar" /><h3>Nothing to report yet</h3></div>
            ) : data.overview_rows.map((row, i) => (
              <OverviewRow key={i} label={row.name} sub={row.context} chip={row.status_label} chipTone={row.status_kind} onOpen={() => router.push(row.link)} />
            ))}
          </div>
        </div>

        <div className="module-card">
          <div className="mc-head">
            <div className="mc-title">Quick actions</div>
            <div className="mc-sub">Common tasks for your current role.</div>
          </div>
          <div className="quick-grid">
            <QuickActionTile title="Headcount report" sub="Employees by unit and location" onClick={() => router.push("/dashboard/employees")} />
            <QuickActionTile title="New joiners" sub="Onboarding and probation" onClick={() => router.push("/dashboard/employees")} />
            <QuickActionTile title="Leave utilization" sub="Balances and trends" onClick={() => router.push("/dashboard/leave?tab=analytics")} />
            <QuickActionTile title="Compensation summary" sub="Restricted to payroll roles" onClick={() => router.push("/dashboard/payroll")} />
          </div>
          <WeeklyBarChart data={data?.weekly_chart ?? []} />
        </div>
      </div>
    </div>
  );
}
