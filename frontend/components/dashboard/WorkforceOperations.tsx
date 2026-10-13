"use client";

// The operational sections that sit under the Workforce dashboard's KPI row:
// platform banner, lifecycle action register, module capability cards,
// operational tools and platform safeguards.
//
// Every figure here is fetched from a real endpoint (nothing is hard-coded or
// randomly generated). Where the signed-in user lacks permission for an
// endpoint (HTTP 403) that card/pill is simply left out instead of showing a
// made-up value. Static text is limited to labels and descriptions of
// where each link goes.

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { DashboardOverview, LifecycleActionRow } from "@/types/dashboard";
import { Skel, WfIcon } from "@/components/dashboard/WorkforceWidgets";

type Tone = "brand" | "ok" | "warn" | "crit" | "info";

const ico = (children: ReactNode) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
);
const Icon = {
  briefcase: ico(<><rect x="3" y="7" width="18" height="13" rx="2.5" /><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3 13h18" /></>),
  star: ico(<path d="m12 3 2.6 5.6 6.1.8-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6L3.3 9.4l6.1-.8z" />),
  gear: ico(<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2 2 2 0 1 1-4 0 1.7 1.7 0 0 0-2.9-1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3 15a2 2 0 1 1 0-4 1.7 1.7 0 0 0 1.2-2.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 10 4.1a2 2 0 1 1 4 0 1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 21 11a2 2 0 1 1 0 4z" /></>),
  chart: ico(<path d="M5 20V10M12 20V4M19 20v-7" />),
  megaphone: ico(<><path d="M4 10v4a1 1 0 0 0 1 1h2l5 4V5L7 9H5a1 1 0 0 0-1 1z" /><path d="M16 9a4 4 0 0 1 0 6" /></>),
  folder: ico(<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />),
  sparkle: ico(<><path d="M12 3v4M12 17v4M3 12h4M17 12h4" /><path d="m6.3 6.3 2.1 2.1M15.6 15.6l2.1 2.1M17.7 6.3l-2.1 2.1M8.4 15.6l-2.1 2.1" /></>),
  inboxCheck: ico(<><path d="M4 13.5 6.4 6.6A2 2 0 0 1 8.3 5.2h7.4a2 2 0 0 1 1.9 1.4L20 13.5V17a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" /><path d="m9 12 2 2 4-4" /></>),
};

interface RecruitmentFunnel { interviews_scheduled: number; interviewed: number; selected: number; details_submitted: number; onboarded: number }
interface AttendanceOverview { present: number; present_pct: number; on_leave: number; late_arrivals: number; missing_punch: number }
interface LeaveOverview { pending: number; on_leave_today: number; upcoming: number }
interface PayrollOverview { blocked: number; cycle_label: string; cycle_status_display: string; employee_count: number }
interface PerformanceOverview { active_cycle: string; self_reviews_pct: number; goals_at_risk: number }
interface ReportsOverview { exports_today: number; audit_events_30d: number }
interface SettingsOverview { admin_roles: number; audit_events_30d: number }
interface SystemHealth { api_status: boolean | string; database_status: boolean | string; mail_status: boolean | string; storage_status: boolean | string }

const isOn = (v: boolean | string | undefined) => v === true || v === "ok" || v === "online" || v === "connected";

function fmtDate(iso: string): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

interface Props { overview: DashboardOverview | null; overviewLoading: boolean }

export default function WorkforceOperations({ overview, overviewLoading }: Props) {
  const router = useRouter();

  const register = useFetch<LifecycleActionRow[]>(API.dashboard.lifecycleRegister);
  const funnel = useFetch<RecruitmentFunnel>(API.dashboard.hrRecruitmentFunnel);
  const attendance = useFetch<AttendanceOverview>(API.dashboard.attendanceOverview);
  const leave = useFetch<LeaveOverview>(API.dashboard.leaveOverview);
  const payroll = useFetch<PayrollOverview>(API.dashboard.payrollOverview);
  const performance = useFetch<PerformanceOverview>(API.dashboard.performanceOverview);
  const reports = useFetch<ReportsOverview>(API.dashboard.reportsOverview);
  const settings = useFetch<SettingsOverview>(API.dashboard.settingsOverview);
  // Admin-only endpoint — HR users get a 403, in which case the health pills are omitted.
  const health = useFetch<SystemHealth>(API.dashboard.kpis);

  // "Last synced" stamp for the banner badge; set client-side after the first overview load.
  const [syncedAt, setSyncedAt] = useState<Date | null>(null);
  useEffect(() => { if (!overviewLoading && overview) setSyncedAt(new Date()); }, [overviewLoading, overview]);

  const rows = register.data ?? [];

  // ── Capability coverage: one card per module, each with a live figure ──
  type Cap = { key: string; name: string; blurb: string; icon: ReactNode; tone: Tone; href: string; loading: boolean; hidden: boolean; metric: string | number; metricLabel: string; note: string };
  const caps: Cap[] = ([
    { key: "recruit", name: "Recruitment", blurb: "Candidates, interviews and offers.", icon: Icon.briefcase, tone: "brand", href: "/dashboard/interview-list",
      loading: funnel.loading, hidden: funnel.status === 403, metric: funnel.data?.selected ?? 0, metricLabel: "candidates selected", note: `${funnel.data?.interviews_scheduled ?? 0} interviews scheduled` },
    { key: "people", name: "Employees", blurb: "Records, profiles and documents.", icon: WfIcon.people, tone: "info", href: "/dashboard/employees",
      loading: overviewLoading, hidden: false, metric: overview?.total_headcount ?? 0, metricLabel: "active employees", note: `${overview?.new_this_month ?? 0} joined this month` },
    { key: "attendance", name: "Attendance", blurb: "Presence, shifts and exceptions.", icon: WfIcon.clock, tone: "ok", href: "/dashboard/attendance",
      loading: attendance.loading, hidden: attendance.status === 403, metric: `${attendance.data?.present_pct ?? 0}%`, metricLabel: "present today", note: `${attendance.data?.late_arrivals ?? 0} late · ${attendance.data?.missing_punch ?? 0} missing punch` },
    { key: "leave", name: "Leave", blurb: "Requests, balances and holidays.", icon: WfIcon.calendar, tone: "info", href: "/dashboard/leave",
      loading: leave.loading, hidden: leave.status === 403, metric: leave.data?.pending ?? 0, metricLabel: "requests pending", note: `${leave.data?.on_leave_today ?? 0} on leave today` },
    { key: "payroll", name: "Payroll", blurb: "Pay cycles, payslips and checks.", icon: WfIcon.wallet, tone: "warn", href: "/dashboard/payroll",
      loading: payroll.loading, hidden: payroll.status === 403, metric: payroll.data?.blocked ?? 0, metricLabel: "records blocked", note: payroll.data?.cycle_label ?? "" },
    { key: "performance", name: "Performance", blurb: "Review cycles, goals and feedback.", icon: Icon.star, tone: "brand", href: "/dashboard/performance",
      loading: performance.loading, hidden: performance.status === 403, metric: `${performance.data?.self_reviews_pct ?? 0}%`, metricLabel: "self-reviews done", note: performance.data?.active_cycle ?? "" },
    { key: "reports", name: "Reports", blurb: "Workforce analytics and exports.", icon: Icon.chart, tone: "info", href: "/dashboard/reports",
      loading: reports.loading, hidden: reports.status === 403, metric: reports.data?.exports_today ?? 0, metricLabel: "exports today", note: `${reports.data?.audit_events_30d ?? 0} audit events (30 days)` },
    { key: "settings", name: "Settings", blurb: "Roles, policies and configuration.", icon: Icon.gear, tone: "crit", href: "/dashboard/settings",
      loading: settings.loading, hidden: settings.status === 403, metric: settings.data?.admin_roles ?? 0, metricLabel: "active roles", note: `${settings.data?.audit_events_30d ?? 0} audit events (30 days)` },
  ] as Cap[]).filter((c) => !c.hidden);

  // ── Operational tools: shortcuts to the working screens, with live counts ──
  const o = overview;
  const tools: { title: string; sub: string; icon: ReactNode; tone: Tone; href: string; live?: boolean; badge?: { text: string; tone: "ok" | "warn" | "crit" } }[] = [
    { title: "Approval inbox", sub: "Review pending leave, expense and onboarding requests.", icon: Icon.inboxCheck, tone: "warn", href: "/dashboard/approvals", live: true,
      badge: o ? { text: `${o.open_requests} pending`, tone: o.open_requests > 0 ? "warn" : "ok" } : undefined },
    { title: "Onboarding queue", sub: "Track new joiners from offer to day one.", icon: WfIcon.userPlus, tone: "brand", href: "/dashboard/candidate-review", live: true,
      badge: o ? { text: `${o.onboarding_in_progress} in progress`, tone: o.onboarding_in_progress > 0 ? "warn" : "ok" } : undefined },
    { title: "Payroll data checks", sub: "Resolve missing bank details and salary setup.", icon: WfIcon.wallet, tone: "info", href: "/dashboard/payroll", live: true,
      badge: o ? { text: `${o.payroll_blocked} blocked`, tone: o.payroll_blocked > 0 ? "crit" : "ok" } : undefined },
    { title: "Compliance documents", sub: "Chase missing statutory and identity documents.", icon: Icon.folder, tone: "ok", href: "/dashboard/documents", live: true,
      badge: o ? { text: `${o.compliance_pct}% complete`, tone: o.compliance_pct >= 90 ? "ok" : "warn" } : undefined },
    { title: "Holiday calendar", sub: "Maintain holidays and leave credit rules.", icon: WfIcon.calendar, tone: "crit", href: "/dashboard/settings/holiday-calendar" },
    { title: "Announcements", sub: "Publish company-wide updates and notices.", icon: Icon.megaphone, tone: "brand", href: "/dashboard/announcements" },
  ];

  // ── Platform safeguards: real health / audit signals ──
  type Pill = { label: string; ok: boolean };
  const pills: Pill[] = [];
  if (health.status !== 403 && health.data) {
    pills.push(
      { label: isOn(health.data.api_status) ? "API online" : "API unreachable", ok: isOn(health.data.api_status) },
      { label: isOn(health.data.database_status) ? "Database connected" : "Database unreachable", ok: isOn(health.data.database_status) },
      { label: isOn(health.data.mail_status) ? "Email configured" : "Email not configured", ok: isOn(health.data.mail_status) },
      { label: isOn(health.data.storage_status) ? "File storage configured" : "File storage not configured", ok: isOn(health.data.storage_status) },
    );
  }
  if (reports.data) {
    pills.push(
      { label: `${reports.data.audit_events_30d} audit events retained (30 days)`, ok: true },
      { label: `${reports.data.exports_today} permission-checked exports today`, ok: true },
    );
  }
  if (overview) {
    pills.push({ label: `${overview.compliance_pct}% document compliance`, ok: overview.compliance_pct >= 90 });
  }
  const pillsLoading = health.loading || reports.loading || overviewLoading;

  return (
    <>
      <div className="wf-banner wf-reveal" style={{ animationDelay: "0.22s" }}>
        <span className="wf-ico brand lg">{Icon.sparkle}</span>
        <div className="wf-banner-txt">
          <b>AIRA · Artificial Intelligence Resources Assistance</b>
          <p>Recruit-to-retire HR operations · effective-dated records · controlled approvals · complete audit trail</p>
        </div>
        <span className="wf-live" title="Figures on this page are read live from your HRMS database">
          <i aria-hidden="true" />LIVE DATA{syncedAt && <small>· updated {syncedAt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</small>}
        </span>
      </div>

      <section className="wf-card wf-reveal" style={{ animationDelay: "0.26s" }}>
        <header className="wf-card-head wf-card-head-row">
          <div>
            <h2>Lifecycle action register &amp; approval inbox</h2>
            <p>Every action retains its effective date, owner, state and decision history.</p>
          </div>
          {!register.loading && register.status !== 403 && <span className="wf-count">{rows.length} open</span>}
        </header>
        <div className="wf-table" role="table" aria-label="Lifecycle action register">
          <div className="wf-tr wf-th" role="row">
            <span>CASE / EMPLOYEE</span><span>ACTION</span><span>EFFECTIVE</span><span>OWNER / STATE</span><span className="r">DECISION</span>
          </div>
          {register.loading && [0, 1, 2].map((i) => (
            <div className="wf-tr" key={i} role="row"><Skel w="70%" h={14} /><Skel w="60%" h={14} /><Skel w="50%" h={14} /><Skel w="60%" h={14} /><Skel w={70} h={30} /></div>
          ))}
          {!register.loading && register.status === 403 && <div className="wf-empty">You don&apos;t have access to the lifecycle register.</div>}
          {!register.loading && register.status !== 403 && register.error && <div className="wf-empty">Couldn&apos;t load the register. <button type="button" className="wf-link" onClick={register.refetch}>Retry</button></div>}
          {!register.loading && !register.error && rows.length === 0 && (
            <div className="wf-empty ok">{WfIcon.check}<span>All clear — no pending separations or onboarding approvals.</span></div>
          )}
          {!register.loading && rows.map((r) => (
            <div className="wf-tr" key={r.case_ref} role="row">
              <span className="wf-case"><b>{r.case_ref}</b><small>{r.employee_name}</small></span>
              <span>{r.action}</span>
              <span>{fmtDate(r.effective)}</span>
              <span className="wf-owner">{r.owner}<em className={`wf-chip ${r.state === "In Progress" ? "info" : "warn"}`}>{r.state}</em></span>
              <span className="r"><button type="button" className="wf-btn sm" onClick={() => router.push(r.link)}>Review {WfIcon.chevron}</button></span>
            </div>
          ))}
        </div>
      </section>

      <section className="wf-card wf-reveal" style={{ animationDelay: "0.3s" }}>
        <header className="wf-card-head">
          <h2>Complete capability coverage</h2>
          <p>Lifecycle functions designed for multi-year HR operations — with live status from each module.</p>
        </header>
        <div className="wf-cap-grid">
          {caps.map((c) => (
            <button type="button" className="wf-cap" key={c.key} onClick={() => router.push(c.href)}>
              <span className="wf-cap-top"><span className={`wf-ico ${c.tone}`}>{c.icon}</span><span className="wf-cap-go">{WfIcon.chevron}</span></span>
              <b>{c.name}</b>
              <small>{c.blurb}</small>
              <span className="wf-cap-metric">
                {c.loading ? <Skel w={56} h={26} /> : <strong>{c.metric}</strong>}
                <em>{c.metricLabel}</em>
              </span>
              <span className="wf-cap-note">{c.loading ? <Skel w={110} h={10} /> : c.note || " "}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="wf-card wf-reveal" style={{ animationDelay: "0.34s" }}>
        <header className="wf-card-head">
          <h2>Operational tools</h2>
          <p>Role-aware tools with effective dates, approval states and audit events.</p>
        </header>
        <div className="wf-tool-grid">
          {tools.map((t) => (
            <article className="wf-tool" key={t.title}>
              <div className="wf-tool-top">
                <span className={`wf-ico ${t.tone}`}>{t.icon}</span>
                {t.live && overviewLoading
                  ? <Skel w={72} h={22} />
                  : t.badge && <span className={`wf-chip ${t.badge.tone}`}>{t.badge.text}</span>}
              </div>
              <b>{t.title}</b>
              <small>{t.sub}</small>
              <button type="button" className="wf-btn" onClick={() => router.push(t.href)}>Launch {WfIcon.chevron}</button>
            </article>
          ))}
        </div>
      </section>

      <section className="wf-card wf-reveal" style={{ animationDelay: "0.38s" }}>
        <header className="wf-card-head">
          <h2>Platform safeguards</h2>
          <p>Live checks that keep long-running HR operations from becoming blocked.</p>
        </header>
        <div className="wf-pills">
          {pillsLoading && pills.length === 0 && [150, 170, 140, 190].map((w) => <Skel key={w} w={w} h={30} />)}
          {pills.map((p) => <span key={p.label} className={`wf-pill ${p.ok ? "ok" : "crit"}`}><i aria-hidden="true" />{p.label}</span>)}
          {!pillsLoading && pills.length === 0 && <span className="wf-empty">No health signals available for your role.</span>}
        </div>
      </section>
    </>
  );
}
