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
  present: number; present_pct: number; on_leave: number; late_arrivals: number; missing_punch: number;
  total_employees: number;
  overview_rows: OverviewRowData[]; weekly_chart: { label: string; count: number }[];
}

const CAPABILITIES = [
  { title: "Time capture", desc: "Device, web, mobile and integration-ready punch sources.", href: "/dashboard/attendance" },
  { title: "Shift planning", desc: "Fixed, rotational, flexi and overnight schedules.", href: "/dashboard/attendance?tab=weekly-off" },
  { title: "Regularization", desc: "Missing punch, late arrival, work-from-home and duty corrections.", href: "/dashboard/attendance?tab=unpunches" },
  { title: "Rules engine", desc: "Grace, overtime, breaks, weekly offs and holiday treatment.", href: "/dashboard/settings" },
  { title: "Exceptions", desc: "Daily anomaly queue with manager and HR resolution.", href: "/dashboard/attendance?tab=invalid" },
  { title: "Period lock", desc: "Validated monthly attendance freeze before payroll.", href: "/dashboard/payroll" },
  { title: "Field attendance", desc: "Location-aware duty and client-site tracking.", href: "/dashboard/attendance" },
  { title: "Auditability", desc: "Original punches retained beside approved corrections.", href: "/dashboard/settings/audit" },
];

const OPERATIONAL_TOOLS = [
  { title: "Open exception queue", desc: "Resolve missing punches and late arrivals.", href: "/dashboard/attendance?tab=invalid" },
  { title: "Create roster", desc: "Assign shifts across a team or location.", href: "/dashboard/attendance?tab=weekly-off" },
  { title: "Regularize entry", desc: "Submit a dated correction with evidence.", href: "/dashboard/attendance?tab=unpunches" },
  { title: "Lock attendance period", desc: "Freeze approved monthly inputs for payroll.", href: "/dashboard/payroll" },
  { title: "Device reconciliation", desc: "Compare imported and recorded punches.", href: "/dashboard/attendance" },
  { title: "Overtime approval", desc: "Review eligible hours and cost impact.", href: "/dashboard/attendance?tab=ot" },
];

export default function AttendanceOverviewClient({ onOpen }: { onOpen: (tab?: string) => void }) {
  const router = useRouter();
  const { data } = useFetch<OverviewData>(API.dashboard.attendanceOverview);

  function go(href: string) {
    if (href.startsWith("/dashboard/attendance")) {
      const tab = new URL(href, "http://x").searchParams.get("tab") ?? undefined;
      onOpen(tab);
    } else {
      router.push(href);
    }
  }

  return (
    <div>
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>Dashboard / Time / Attendance</div>
      <div className="pagehead">
        <div>
          <h1>Attendance <em>today</em></h1>
          <p className="lede">
            Track presence, shifts, regularization requests and location-level exceptions.
          </p>
        </div>
        <button className="btn btn-filled" onClick={() => onOpen("unpunches")}>Regularize attendance</button>
      </div>

      <div className="stats">
        <KpiTile label="PRESENT" value={data?.present ?? "—"} sub={data ? `${data.present_pct}% of headcount` : ""} tone="ok" />
        <KpiTile label="ON LEAVE" value={data?.on_leave ?? "—"} sub="Approved requests" tone="brand" />
        <KpiTile label="LATE ARRIVALS" value={data?.late_arrivals ?? "—"} sub="Needs review" tone="warn" />
        <KpiTile label="MISSING PUNCH" value={data?.missing_punch ?? "—"} sub="Action required" tone="crit" />
      </div>

      <div className="module-grid">
        <div className="module-card">
          <div className="mc-head">
            <div className="mc-title">Attendance overview</div>
            <div className="mc-sub">Current records and items requiring attention.</div>
          </div>
          <div style={{ padding: "0 20px 4px" }}>
            {!data || data.overview_rows.length === 0 ? (
              <div className="empty-state"><i className="ti ti-clock" /><h3>No records yet today</h3></div>
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
            <QuickActionTile title="Daily attendance" sub={data ? `${data.total_employees} employee register` : "Employee register"} onClick={() => onOpen()} />
            <QuickActionTile title="Shift roster" sub="Standard and field schedules" onClick={() => onOpen("weekly-off")} />
            <QuickActionTile title="Regularization queue" sub={data ? `${data.missing_punch} pending requests` : "Pending requests"} onClick={() => onOpen("unpunches")} />
            <QuickActionTile title="Monthly summary" sub={new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" })} onClick={() => onOpen()} />
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
