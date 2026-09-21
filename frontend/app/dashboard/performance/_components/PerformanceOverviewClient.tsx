"use client";

import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { KpiTile, OverviewRow, QuickActionTile, WeeklyBarChart } from "@/components/dashboard/ModuleOverviewKit";

interface OverviewRowData { name: string; context: string; status_label: string; status_kind: "success" | "error" | "warn"; link: string }
interface OverviewData {
  active_cycle: string; active_cycle_closes: string;
  self_reviews_done: number; self_reviews_total: number; self_reviews_pct: number;
  manager_reviews_done: number; manager_reviews_total: number; manager_reviews_pct: number;
  goals_at_risk: number; my_review_tasks: number; active_goals: number;
  overview_rows: OverviewRowData[]; weekly_chart: { label: string; count: number }[];
}

export default function PerformanceOverviewClient({ onOpen }: { onOpen: () => void }) {
  const router = useRouter();
  const { data } = useFetch<OverviewData>(API.dashboard.performanceOverview);

  function go(href: string) {
    if (href.startsWith("/dashboard/performance")) onOpen();
    else router.push(href);
  }

  return (
    <div>
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>Dashboard / Performance</div>
      <div className="pagehead">
        <div>
          <h1>Performance <em>reviews</em></h1>
          <p className="lede">
            Track goals, check-ins, review cycles and calibration across teams.
          </p>
        </div>
        <button className="btn btn-filled" onClick={onOpen}>Create review cycle</button>
      </div>

      <div className="stats">
        <KpiTile label="ACTIVE CYCLE" value={data?.active_cycle ?? "—"} sub={data?.active_cycle_closes ?? ""} tone="brand" />
        <KpiTile label="SELF REVIEWS" value={data?.self_reviews_done ?? "—"} sub={data ? `${data.self_reviews_pct}% complete` : ""} tone="ok" />
        <KpiTile label="MANAGER REVIEWS" value={data?.manager_reviews_done ?? "—"} sub={data ? `${data.manager_reviews_pct}% complete` : ""} tone="ok" />
        <KpiTile label="GOALS AT RISK" value={data?.goals_at_risk ?? "—"} sub="Needs follow-up" tone="crit" />
      </div>

      <div className="module-grid">
        <div className="module-card">
          <div className="mc-head">
            <div className="mc-title">Performance overview</div>
            <div className="mc-sub">Current records and items requiring attention.</div>
          </div>
          <div style={{ padding: "0 20px 4px" }}>
            {!data || data.overview_rows.length === 0 ? (
              <div className="empty-state"><i className="ti ti-report" /><h3>No active cycle</h3></div>
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
            <QuickActionTile title="My review tasks" sub={data ? `${data.my_review_tasks} assigned items` : "Assigned items"} onClick={onOpen} />
            <QuickActionTile title="Team goals" sub={data ? `${data.active_goals} active goals` : "Active goals"} onClick={onOpen} />
            <QuickActionTile title="Feedback" sub="Request or give feedback" onClick={onOpen} />
            <QuickActionTile title="Review templates" sub="Quarterly · Probation · Annual" onClick={onOpen} />
          </div>
          <WeeklyBarChart data={data?.weekly_chart ?? []} />
        </div>
      </div>
    </div>
  );
}
