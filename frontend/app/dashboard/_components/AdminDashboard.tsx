"use client";

import KpiConsole            from "@/components/dashboard/KpiConsole";
import AnnouncementCard      from "@/components/dashboard/AnnouncementCard";
import PendingApprovalsWidget from "@/components/dashboard/PendingApprovalsWidget";
import DeptHeadcountChart    from "@/components/dashboard/DeptHeadcountChart";
import EmployeeLifecycleTabs from "@/components/dashboard/EmployeeLifecycleTabs";
import BirthdayWidget        from "@/components/dashboard/BirthdayWidget";
import AuditLogsWidget       from "@/components/dashboard/AuditLogsWidget";
import { KpiCard, AttendanceTrend, AttendanceInsights, WfIcon } from "@/components/dashboard/WorkforceWidgets";
import WorkforceOperations   from "@/components/dashboard/WorkforceOperations";
import { HeadcountTrendCard, LeaveTrendCard, PayrollCostTrendCard } from "@/components/dashboard/TrendCharts";
import { useDashboardOverview } from "@/hooks/useDashboardOverview";
import { useRouter } from "next/navigation";
import type { SessionPayload } from "@/lib/session";

const pct = (part: number, whole: number) => (whole > 0 ? (part / whole) * 100 : null);

interface Props { session: SessionPayload }

interface QuickAction {
  href:  string;
  icon:  string;
  bg:    string;
  color: string;
  label: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  { href: "/dashboard/employees",            icon: "ti-id-badge",            bg: "rgba(124,58,237,0.12)",  color: "var(--primary)", label: "Employees"     },
  { href: "/dashboard/settings/access", icon: "ti-shield-check",        bg: "rgba(23,144,90,0.12)", color: "var(--success)", label: "Permissions" },
  { href: "/dashboard/attendance",           icon: "ti-clock",               bg: "rgba(37,99,235,0.12)", color: "var(--info)",    label: "Attendance"    },
  { href: "/dashboard/payroll",              icon: "ti-report-money",        bg: "rgba(162,98,12,0.12)", color: "var(--warn)",    label: "Payroll"       },
  { href: "/dashboard/branches",             icon: "ti-building-skyscraper", bg: "rgba(124,58,237,0.12)",  color: "var(--primary)", label: "Company Codes" },
  { href: "/dashboard/settings",             icon: "ti-settings",            bg: "rgba(162,98,12,0.12)", color: "var(--warn)",    label: "Settings"      },
];

export default function AdminDashboard({ session }: Props) {
  const firstName = session.name.split(" ")[0];
  const router = useRouter();
  // Same company-wide workforce analytics the Workforce (HR) Dashboard
  // shows — a superuser holds every permission those widgets check, so
  // nothing here is hidden; this is strictly additive to KpiConsole's own
  // branch/approval/onboarding health pills below, not a replacement.
  const { data: overview, loading: overviewLoading } = useDashboardOverview();
  const totalHeadcount = overview?.total_headcount ?? 0;
  const presentToday = overview?.present_today ?? 0;
  const attendancePct = overview?.attendance_pct ?? 0;
  const payrollReady = overview?.payroll_ready ?? 0;
  const payrollTotal = overview?.payroll_total ?? 0;
  const payrollBlocked = overview?.payroll_blocked ?? 0;

  return (
    <>
      {/* KPI Console — welcome + health pills + live stats */}
      <KpiConsole firstName={firstName} />

      {/* Company-wide workforce analytics — headcount, attendance, payroll readiness */}
      <div className="wf-stats mb-20">
        <KpiCard
          label="TOTAL HEADCOUNT" icon={WfIcon.people} tone="brand" loading={overviewLoading}
          value={totalHeadcount} sub="company-wide"
          onClick={() => router.push("/dashboard/employees")}
        />
        <KpiCard
          label="PRESENT TODAY" icon={WfIcon.check} tone="ok" loading={overviewLoading}
          value={presentToday} sub={`${attendancePct}% attendance`}
          progress={attendancePct}
          onClick={() => router.push("/dashboard/attendance")}
        />
        <KpiCard
          label="PAYROLL READY" icon={WfIcon.wallet} tone="info" loading={overviewLoading}
          value={payrollReady} sub={`${payrollBlocked} records blocked`}
          trend={payrollBlocked > 0 ? { text: "Action", tone: "warn" } : null}
          progress={pct(payrollReady, payrollTotal)}
          onClick={() => router.push("/dashboard/payroll")}
        />
      </div>

      <div className="card mb-20">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-chart-line" /> Attendance this week</div>
        </div>
        <div className="card-body wf-week">
          <AttendanceTrend data={overview?.weekly_attendance ?? []} total={totalHeadcount} loading={overviewLoading} />
          <AttendanceInsights data={overview?.weekly_attendance ?? []} total={totalHeadcount} loading={overviewLoading} />
        </div>
      </div>

      <WorkforceOperations overview={overview ?? null} overviewLoading={overviewLoading} />

      {/* Historical trends — headcount growth, leave approvals/rejections, payroll cost */}
      <div className="grid-2 mb-20">
        <HeadcountTrendCard />
        <LeaveTrendCard />
      </div>
      <div className="mb-20">
        <PayrollCostTrendCard />
      </div>

      {/* Announcement */}
      <AnnouncementCard />

      {/* Quick Actions */}
      <div className="card mb-20">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-bolt" /> Quick Actions</div>
        </div>
        <div className="card-body">
          <div className="qa-grid">
            {QUICK_ACTIONS.map(a => (
              <a key={a.href} href={a.href} className="qa-tile">
                <div className="qa-icon" style={{ background: a.bg, color: a.color }}>
                  <i className={`ti ${a.icon}`} />
                </div>
                <span className="qa-label">{a.label}</span>
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* Row 3 — Pending Approvals + Headcount | Announcement + Lifecycle */}
      <div className="grid-2 mb-20">
        <div>
          <PendingApprovalsWidget />
          <DeptHeadcountChart />
        </div>
        <div>
          <EmployeeLifecycleTabs />
        </div>
      </div>

      {/* Row 4 — Birthdays | Audit Logs */}
      <div className="grid-2">
        <div>
          <BirthdayWidget />
        </div>
        <div>
          <AuditLogsWidget />
        </div>
      </div>
    </>
  );
}
