"use client";

// The operational sections under the Workforce dashboard's KPI, overview and analytics rows: the lifecycle action register
// (work waiting on a decision) and a slim strip of platform safeguards.
//
// Every figure here is fetched from a real endpoint (nothing is hard-coded or randomly generated). Where the signed-in
// user lacks permission for an endpoint (HTTP 403) that pill is simply left out instead of showing a made-up value.
// The module shortcut tiles and the AIRA banner that used to sit here were removed: they repeated the top menu, the
// Quick actions and the KPI row, and cost a request per module.

import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import type { DashboardOverview, LifecycleActionRow } from "@/types/dashboard";
import { Skel, WfIcon } from "@/components/dashboard/WorkforceWidgets";

interface ReportsOverview { exports_today: number; audit_events_30d: number }
interface SystemHealth { api_status: boolean | string; database_status: boolean | string; mail_status: boolean | string; storage_status: boolean | string }

const isOn = (v: boolean | string | undefined) => v === true || v === "ok" || v === "online" || v === "connected";

function fmtDate(iso: string): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

type Pill = { label: string; ok: boolean; href?: string };

function safeguardPills(
  health: SystemHealth | null, reports: ReportsOverview | null, overview: DashboardOverview | null,
  holidays: { total: number } | null, year: number,
): Pill[] {
  const pills: Pill[] = [];
  if (health) {
    pills.push(
      { label: isOn(health.api_status) ? "API online" : "API unreachable", ok: isOn(health.api_status) },
      { label: isOn(health.database_status) ? "Database connected" : "Database unreachable", ok: isOn(health.database_status) },
      { label: isOn(health.mail_status) ? "Email configured" : "Email not configured", ok: isOn(health.mail_status) },
      { label: isOn(health.storage_status) ? "File storage configured" : "File storage not configured", ok: isOn(health.storage_status) },
    );
  }
  if (reports) {
    pills.push(
      { label: `${reports.audit_events_30d} audit events retained (30 days)`, ok: true, href: "/dashboard/settings/audit" },
      { label: `${reports.exports_today} permission-checked exports today`, ok: true, href: "/dashboard/reports" },
    );
  }
  if (overview) pills.push({ label: `${overview.compliance_pct}% document compliance`, ok: overview.compliance_pct >= 90, href: "/dashboard/documents" });
  if (holidays) {
    const count = holidays.total ?? 0;
    pills.push({
      label: count > 0 ? `${count} holidays configured for ${year}` : `No holidays configured for ${year} — import required`,
      ok: count > 0,
      href: "/dashboard/settings/holiday-calendar",
    });
  }
  return pills;
}

interface Props { overview: DashboardOverview | null; overviewLoading: boolean }

export default function WorkforceOperations({ overview, overviewLoading }: Props) {
  const router = useRouter();

  const register = useFetch<LifecycleActionRow[]>(API.dashboard.lifecycleRegister);
  const reports = useFetch<ReportsOverview>(API.dashboard.reportsOverview);
  // Needs settings.edit: without it the request is not made and the health pills are omitted.
  const canSeeHealth = usePermission("settings.edit");
  const health = useFetch<SystemHealth>(canSeeHealth ? API.dashboard.kpis : null);
  const currentYear = new Date().getFullYear();
  const holidaysThisYear = useFetch<{ holidays: unknown[]; total: number }>(`${API.leave.holidays}?year=${currentYear}`);

  const rows = register.data ?? [];
  const pills = safeguardPills(
    health.status !== 403 ? health.data : null,
    reports.data,
    overview,
    holidaysThisYear.status !== 403 ? holidaysThisYear.data : null,
    currentYear,
  );
  const pillsLoading = health.loading || reports.loading || overviewLoading;

  return (
    <>
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
          <h2>Platform safeguards</h2>
          <p>Live checks that keep long-running HR operations from becoming blocked.</p>
        </header>
        <div className="wf-pills">
          {pillsLoading && pills.length === 0 && [150, 170, 140, 190].map((w) => <Skel key={w} w={w} h={30} />)}
          {pills.map(({ label, ok, href }) => href
            ? <button type="button" key={label} className={`wf-pill link ${ok ? "ok" : "crit"}`} onClick={() => router.push(href)}><i aria-hidden="true" />{label}</button>
            : <span key={label} className={`wf-pill ${ok ? "ok" : "crit"}`}><i aria-hidden="true" />{label}</span>)}
          {!pillsLoading && pills.length === 0 && <span className="wf-empty">No health signals available for your role.</span>}
        </div>
      </section>
    </>
  );
}
