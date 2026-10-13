"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { KpiCard, OverviewItem, QuickTile, AttendanceTrend, AttendanceInsights, WfIcon } from "@/components/dashboard/WorkforceWidgets";
import WorkforceOperations from "@/components/dashboard/WorkforceOperations";
import { useDashboardOverview } from "@/hooks/useDashboardOverview";
import { usePermission } from "@/hooks/usePermission";
import type { SessionPayload } from "@/lib/session";

interface Props { session: SessionPayload }

const pct = (part: number, whole: number) => (whole > 0 ? (part / whole) * 100 : null);

export default function HRDashboard({ session }: Props) {
  const router = useRouter();
  const { data, loading } = useDashboardOverview();
  // This dashboard is shown to anyone holding employees.view (or a
  // superuser) — a strictly broader group than employees.create (see
  // app/dashboard/page.tsx's resolveDashboard) — so the "Hire an employee"
  // tile must be gated separately, same as the Employee Directory's own
  // "Hire employee" button. Without this, a view-only HR role saw the tile,
  // clicked it, landed on the directory, and nothing visibly happened — the
  // directory page itself silently no-ops the deep link for a user who
  // can't create employees, rather than erroring.
  const canHire = usePermission("employees.create");

  // Date/greeting depend on the viewer's clock, so they're filled in after
  // mount — computing them during render would risk a server/client mismatch.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);

  const monthLabel = new Date().toLocaleDateString("en-IN", { month: "long", year: "numeric" });
  const hour = now?.getHours() ?? 12;
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const firstName = (session?.name ?? "").trim().split(/\s+/)[0];
  const dateLabel = now?.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" }) ?? "";

  const totalHeadcount = data?.total_headcount ?? 0;
  const presentToday = data?.present_today ?? 0;
  const payrollReady = data?.payroll_ready ?? 0;
  const payrollTotal = data?.payroll_total ?? 0;
  const payrollBlocked = data?.payroll_blocked ?? 0;
  const openRequests = data?.open_requests ?? 0;
  const newThisMonth = data?.new_this_month ?? 0;
  const attendancePct = data?.attendance_pct ?? 0;
  const exceptions = data?.attendance_exceptions_today ?? 0;
  const compliancePct = data?.compliance_pct ?? 0;

  const quickActions = [
    canHire && { title: "Hire an employee", sub: "Start the guided onboarding flow", href: "/dashboard/employees?action=hire", icon: WfIcon.userPlus, tone: "brand" as const },
    { title: "Review leave", sub: `${openRequests} requests need a decision`, href: "/dashboard/approvals", icon: WfIcon.calendar, tone: "info" as const },
    { title: "Run payroll checks", sub: `Resolve ${payrollBlocked} blocked records`, href: "/dashboard/payroll", icon: WfIcon.wallet, tone: "warn" as const },
    { title: "Export workforce report", sub: "Download the current snapshot", href: "/dashboard/reports", icon: WfIcon.report, tone: "ok" as const },
  ].filter((a): a is Exclude<typeof a, false> => Boolean(a));

  return (
    <div className="wf-dashboard">
      <div className="wf-pagehead wf-reveal" style={{ animationDelay: "0.02s" }}>
        <div className="wf-titleblock">
          <div className="wf-eyebrow">Dashboard / Overview{dateLabel && <> <span aria-hidden="true">·</span> {dateLabel}</>}</div>
          <h1>Workforce <em className="hl">dashboard</em></h1>
          <p className="wf-lede">
            {now && firstName ? `${greeting}, ${firstName}. ` : ""}A live view of people operations, payroll readiness and work requiring attention.
          </p>
        </div>
        <div className="wf-headacts">
          <button type="button" className="wf-btn" onClick={() => router.push("/dashboard/reports")}>Export report</button>
          <button type="button" className="wf-btn pri" onClick={() => router.push("/dashboard/approvals")}>Review alerts</button>
        </div>
      </div>

      <div className="wf-stats wf-reveal" style={{ animationDelay: "0.06s" }}>
        <KpiCard
          label="TOTAL HEADCOUNT" icon={WfIcon.people} tone="brand" loading={loading}
          value={totalHeadcount} sub="new this month"
          trend={newThisMonth > 0 ? { text: `+${newThisMonth}`, tone: "ok" } : null}
        />
        <KpiCard
          label="PRESENT TODAY" icon={WfIcon.check} tone="ok" loading={loading}
          value={presentToday} sub={`${attendancePct}% attendance`}
          progress={attendancePct}
        />
        <KpiCard
          label="PAYROLL READY" icon={WfIcon.wallet} tone="info" loading={loading}
          value={payrollReady} sub={`${payrollBlocked} records blocked`}
          trend={payrollBlocked > 0 ? { text: "Action", tone: "warn" } : null}
          progress={pct(payrollReady, payrollTotal)}
        />
        <KpiCard
          label="OPEN REQUESTS" icon={WfIcon.inbox} tone="warn" loading={loading}
          value={openRequests} sub={`${openRequests} awaiting you`}
        />
      </div>

      <div className="wf-modules">
        <section className="wf-card wf-reveal" style={{ animationDelay: "0.1s" }}>
          <header className="wf-card-head">
            <div>
              <h2>Dashboard overview</h2>
              <p>Current records and items requiring attention.</p>
            </div>
          </header>
          <div className="wf-ov-list">
            <OverviewItem
              icon={WfIcon.wallet} tone="info" label="Payroll readiness" loading={loading}
              sub={monthLabel}
              chip={`${payrollReady} of ${payrollTotal} ready`} chipTone={payrollBlocked > 0 ? "warn" : "ok"}
              progress={pct(payrollReady, payrollTotal)}
              onOpen={() => router.push("/dashboard/payroll")}
            />
            <OverviewItem
              icon={WfIcon.userPlus} tone="brand" label="Onboarding" loading={loading}
              sub={`${data?.joining_this_week ?? 0} joining this week`}
              chip={`${data?.onboarding_in_progress ?? 0} in progress`} chipTone="warn"
              onOpen={() => router.push("/dashboard/candidate-review")}
            />
            <OverviewItem
              icon={WfIcon.clock} tone="ok" label="Attendance" loading={loading}
              sub="Today · all locations"
              chip={`${exceptions} exceptions`} chipTone={exceptions > 0 ? "crit" : "ok"}
              progress={attendancePct}
              onOpen={() => router.push("/dashboard/attendance")}
            />
            <OverviewItem
              icon={WfIcon.shield} tone="crit" label="Compliance" loading={loading}
              sub="Statutory declarations"
              chip={`${compliancePct}% complete`} chipTone={compliancePct >= 90 ? "ok" : "warn"}
              progress={compliancePct}
              onOpen={() => router.push("/dashboard/reports")}
            />
          </div>
        </section>

        <section className="wf-card wf-reveal" style={{ animationDelay: "0.14s" }}>
          <header className="wf-card-head">
            <div>
              <h2>Quick actions</h2>
              <p>Common tasks for your current role.</p>
            </div>
          </header>
          <div className="wf-qa-grid">
            {quickActions.map((a) => (
              <QuickTile key={a.title} icon={a.icon} tone={a.tone} title={a.title} sub={a.sub} onClick={() => router.push(a.href)} />
            ))}
          </div>
        </section>
      </div>

      <section className="wf-card wf-reveal" style={{ animationDelay: "0.18s" }}>
        <header className="wf-card-head">
          <div>
            <h2>Attendance this week</h2>
            <p>Employees present each day, as a share of total headcount.</p>
          </div>
        </header>
        <div className="wf-week">
          <AttendanceTrend data={data?.weekly_attendance ?? []} total={totalHeadcount} loading={loading} />
          <AttendanceInsights data={data?.weekly_attendance ?? []} total={totalHeadcount} loading={loading} />
        </div>
      </section>

      <WorkforceOperations overview={data} overviewLoading={loading} />
    </div>
  );
}
