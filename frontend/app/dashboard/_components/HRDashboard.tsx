"use client";

import { useT } from "@/hooks/useI18n";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { KpiCard, OverviewItem, QuickTile, AttendanceTrend, AttendanceInsights, WfIcon } from "@/components/dashboard/WorkforceWidgets";
import WorkforceOperations from "@/components/dashboard/WorkforceOperations";
import DeptHeadcountChart from "@/components/dashboard/DeptHeadcountChart";
import LinkCard from "@/components/dashboard/LinkCard";
import { HeadcountTrendCard, LeaveTrendCard, PayrollCostTrendCard } from "@/components/dashboard/TrendCharts";
import { buildApprovalsLink } from "@/lib/approvalLink";
import { useDashboardOverview } from "@/hooks/useDashboardOverview";
import { usePermission } from "@/hooks/usePermission";
import { useToast } from "@/components/ToastProvider";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { ApiEmployee } from "@/app/dashboard/employees/_data";
import { downloadCsv, employeesToCsv } from "@/lib/exportEmployeesCsv";
import type { SessionPayload } from "@/lib/session";

interface Props { session: SessionPayload }

const pct = (part: number, whole: number) => (whole > 0 ? (part / whole) * 100 : null);

export default function HRDashboard({ session }: Props) {
  const router = useRouter();
  const t = useT();
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
  // Same gate the real Employee Directory export button uses — Payroll
  // Admin and HR hold it, a Reporting Manager does not (see
  // EmployeeDirectoryHeader's own comment on employees.export).
  const canExport = usePermission("employees.export");
  const { showToast } = useToast();
  const [exporting, setExporting] = useState(false);

  // "Export report" — a real, immediate download (the full workforce
  // snapshot, unfiltered), not just a navigation to the Reports hub. Reuses
  // the exact same CSV columns the Employee Directory's own filtered export
  // produces (lib/exportEmployeesCsv.ts) so the two never drift apart.
  async function handleExportReport() {
    setExporting(true);
    try {
      const { data } = await clientApi.get<{ data: { results: ApiEmployee[] } }>(
        API.employees.list, { params: { page: 1, page_size: 1000 } },
      );
      const rows = data.data?.results ?? [];
      downloadCsv(employeesToCsv(rows), `workforce-report-${new Date().toISOString().slice(0, 10)}.csv`);
      showToast(t("Workforce report exported."), "success");
    } catch {
      showToast(t("Could not export the workforce report. Please try again."), "error");
    } finally {
      setExporting(false);
    }
  }

  // Date/greeting depend on the viewer's clock, so they're filled in after
  // mount — computing them during render would risk a server/client mismatch.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);

  const monthLabel = new Date().toLocaleDateString("en-IN", { month: "long", year: "numeric" });
  const hour = now?.getHours() ?? 12;
  const firstName = (session?.name ?? "").trim().split(/\s+/)[0];
  const greeting = hour < 12 ? t("Good morning, {name}. ", { name: firstName }) : hour < 17 ? t("Good afternoon, {name}. ", { name: firstName }) : t("Good evening, {name}. ", { name: firstName });
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
    canHire && { title: t("Hire an employee"), sub: t("Start the guided onboarding flow"), onClick: () => router.push("/dashboard/employees?action=hire"), icon: WfIcon.userPlus, tone: "brand" as const },
    { title: t("Review leave"), sub: t("{count} requests need a decision", { count: openRequests }), onClick: () => router.push("/dashboard/approvals"), icon: WfIcon.calendar, tone: "info" as const },
    { title: t("Run payroll checks"), sub: t("Resolve {count} blocked records", { count: payrollBlocked }), onClick: () => router.push("/dashboard/payroll"), icon: WfIcon.wallet, tone: "warn" as const },
    canExport && { title: t("Export workforce report"), sub: exporting ? t("Exporting…") : t("Download the current snapshot"), onClick: handleExportReport, icon: WfIcon.report, tone: "ok" as const },
  ].filter((a): a is Exclude<typeof a, false> => Boolean(a));

  return (
    <div className="wf-dashboard wf-compact">
      <div className="wf-pagehead wf-reveal" style={{ animationDelay: "0.02s" }}>
        <div className="wf-titleblock">
          <div className="wf-eyebrow">{t("Dashboard / Overview")}{dateLabel && <> <span aria-hidden="true">·</span> {dateLabel}</>}</div>
          <h1>{t("Workforce")} <em className="hl">{t("dashboard")}</em></h1>
          <p className="wf-lede">
            {now && firstName ? greeting : ""}{t("A live view of people operations, payroll readiness and work requiring attention.")}
          </p>
        </div>
        <div className="wf-headacts">
          {canExport && (
            <button type="button" className="wf-btn" onClick={handleExportReport} disabled={exporting}>
              {exporting ? t("Exporting…") : t("Export report")}
            </button>
          )}
          <button type="button" className="wf-btn pri" onClick={() => router.push("/dashboard/approvals")}>{t("Review alerts")}</button>
        </div>
      </div>

      <div className="wf-stats wf-reveal" style={{ animationDelay: "0.06s" }}>
        <KpiCard
          label={t("TOTAL HEADCOUNT")} icon={WfIcon.people} tone="brand" loading={loading}
          value={totalHeadcount} sub={t("new this month")}
          trend={newThisMonth > 0 ? { text: `+${newThisMonth}`, tone: "ok" } : null}
          onClick={() => router.push("/dashboard/employees")}
        />
        <KpiCard
          label={t("PRESENT TODAY")} icon={WfIcon.check} tone="ok" loading={loading}
          value={presentToday} sub={t("{percent}% attendance", { percent: attendancePct })}
          progress={attendancePct}
          onClick={() => router.push("/dashboard/attendance")}
        />
        <KpiCard
          label={t("PAYROLL READY")} icon={WfIcon.wallet} tone="info" loading={loading}
          value={payrollReady} sub={t("{count} records blocked", { count: payrollBlocked })}
          trend={payrollBlocked > 0 ? { text: t("Action"), tone: "warn" } : null}
          progress={pct(payrollReady, payrollTotal)}
          onClick={() => router.push("/dashboard/payroll")}
        />
        <KpiCard
          label={t("OPEN REQUESTS")} icon={WfIcon.inbox} tone="warn" loading={loading}
          value={openRequests} sub={t("{count} awaiting you", { count: openRequests })}
          onClick={() => router.push("/dashboard/approvals")}
        />
      </div>

      <div className="wf-modules">
        <section className="wf-card wf-reveal" style={{ animationDelay: "0.1s" }}>
          <header className="wf-card-head">
            <div>
              <h2>{t("Dashboard overview")}</h2>
              <p>{t("Current records and items requiring attention.")}</p>
            </div>
          </header>
          <div className="wf-ov-list">
            <OverviewItem
              icon={WfIcon.wallet} tone="info" label={t("Payroll readiness")} loading={loading}
              sub={monthLabel}
              chip={t("{ready} of {total} ready", { ready: payrollReady, total: payrollTotal })} chipTone={payrollBlocked > 0 ? "warn" : "ok"}
              progress={pct(payrollReady, payrollTotal)}
              onOpen={() => router.push("/dashboard/payroll")}
            />
            <OverviewItem
              icon={WfIcon.userPlus} tone="brand" label={t("Onboarding")} loading={loading}
              sub={t("{count} joining this week", { count: data?.joining_this_week ?? 0 })}
              chip={t("{count} in progress", { count: data?.onboarding_in_progress ?? 0 })} chipTone="warn"
              onOpen={() => router.push("/dashboard/candidate-review")}
            />
            <OverviewItem
              icon={WfIcon.clock} tone="ok" label={t("Attendance")} loading={loading}
              sub={t("Today · all locations")}
              chip={t("{count} exceptions", { count: exceptions })} chipTone={exceptions > 0 ? "crit" : "ok"}
              progress={attendancePct}
              onOpen={() => router.push("/dashboard/attendance")}
            />
            <OverviewItem
              icon={WfIcon.shield} tone="crit" label={t("Compliance")} loading={loading}
              sub={t("Statutory declarations")}
              chip={t("{percent}% complete", { percent: compliancePct })} chipTone={compliancePct >= 90 ? "ok" : "warn"}
              progress={compliancePct}
              onOpen={() => router.push("/dashboard/reports")}
            />
          </div>
        </section>

        <section className="wf-card wf-reveal" style={{ animationDelay: "0.14s" }}>
          <header className="wf-card-head">
            <div>
              <h2>{t("Quick actions")}</h2>
              <p>{t("Common tasks for your current role.")}</p>
            </div>
          </header>
          <div className="wf-qa-grid">
            {quickActions.map((a) => (
              <QuickTile key={a.title} icon={a.icon} tone={a.tone} title={a.title} sub={a.sub} onClick={a.onClick} />
            ))}
          </div>
        </section>
      </div>

      <section className="wf-reveal" style={{ animationDelay: "0.16s" }} aria-labelledby="wf-analytics-title">
        <header className="wf-analytics-head">
          <h2 id="wf-analytics-title">{t("Analytics")}</h2>
          <p>{t("Where people work, and how headcount, leave and payroll cost have moved over the last six months.")}</p>
        </header>
        <div className="wf-analytics-grid">
          <LinkCard href="/dashboard/employees" label={t("Open employees")}><HeadcountTrendCard /></LinkCard>
          <LinkCard href="/dashboard/employees" label={t("Open employees")}><DeptHeadcountChart /></LinkCard>
          <LinkCard href={buildApprovalsLink({ type: "leave", status: "all" })} label={t("Open leave requests")}><LeaveTrendCard /></LinkCard>
          <LinkCard href="/dashboard/payroll" label={t("Open payroll")}><PayrollCostTrendCard /></LinkCard>
        </div>
      </section>

      <LinkCard href="/dashboard/attendance" label={t("Open attendance")}>
      <section className="wf-card wf-reveal" style={{ animationDelay: "0.18s" }}>
        <header className="wf-card-head">
          <div>
            <h2>{t("Attendance this week")}</h2>
            <p>{t("Employees present each day, as a share of total headcount.")}</p>
          </div>
        </header>
        <div className="wf-week">
          <AttendanceTrend data={data?.weekly_attendance ?? []} total={totalHeadcount} loading={loading} />
          <AttendanceInsights data={data?.weekly_attendance ?? []} total={totalHeadcount} loading={loading} />
        </div>
      </section>
      </LinkCard>

      <WorkforceOperations overview={data} overviewLoading={loading} />
    </div>
  );
}
