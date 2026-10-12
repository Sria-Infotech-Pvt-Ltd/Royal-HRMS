"use client";

// Presentation widgets for the Workforce dashboard (HRDashboard.tsx). They only
// render the values they are given — every number comes from the dashboard
// overview endpoint, nothing here invents data. Styles live in aira-theme.css
// under the `.wf-` prefix.

import type { ReactNode } from "react";

type Tone = "brand" | "ok" | "warn" | "crit" | "info";

const svg = (children: ReactNode) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

export const WfIcon = {
  people: svg(<><circle cx="9" cy="8" r="3.2" /><path d="M3 20c0-3.1 2.7-5 6-5s6 1.9 6 5" /><path d="M16.5 5.2a3 3 0 0 1 0 5.6M18 15.3c1.9.6 3 2.2 3 4.7" /></>),
  check: svg(<><circle cx="12" cy="12" r="8.5" /><path d="m8.5 12.2 2.4 2.4 4.6-5" /></>),
  wallet: svg(<><rect x="3" y="6" width="18" height="13" rx="2.5" /><path d="M3 10h18M16 14.5h2" /></>),
  inbox: svg(<><path d="M4 13.5 6.4 6.6A2 2 0 0 1 8.3 5.2h7.4a2 2 0 0 1 1.9 1.4L20 13.5" /><path d="M4 13.5V17a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3.5h-4.5a2 2 0 0 1-1.8 1.1h-3.4a2 2 0 0 1-1.8-1.1z" /></>),
  userPlus: svg(<><circle cx="9" cy="8" r="3.2" /><path d="M3 20c0-3.1 2.7-5 6-5s6 1.9 6 5" /><path d="M18 8v6M15 11h6" /></>),
  clock: svg(<><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>),
  shield: svg(<><path d="M12 3 4.5 6v5.5c0 4.4 3.1 8 7.5 9.5 4.4-1.5 7.5-5.1 7.5-9.5V6z" /><path d="m9 12 2.2 2.2L15 10" /></>),
  calendar: svg(<><rect x="3" y="5" width="18" height="16" rx="2.5" /><path d="M8 3v4M16 3v4M3 10h18" /></>),
  report: svg(<><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4M9 13h6M9 17h4" /></>),
  chevron: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>,
};

/** Shimmering placeholder shown while the overview request is in flight. */
export function Skel({ w = 56, h = 14 }: { w?: number | string; h?: number }) {
  return <span className="wf-skel" style={{ width: w, height: h }} aria-hidden="true" />;
}

export function KpiCard({ label, icon, tone, loading, value, sub, trend, progress }: {
  label: string;
  icon: ReactNode;
  tone: Tone;
  loading: boolean;
  value: string | number;
  sub: string;
  /** Short coloured chip next to the sub-line (e.g. "+3"). */
  trend?: { text: string; tone: Tone } | null;
  /** 0–100 — renders a thin meter under the number. Omit when there's no real ratio. */
  progress?: number | null;
}) {
  return (
    <div className="wf-kpi">
      <div className="wf-kpi-top">
        <span className="wf-kpi-label">{label}</span>
        <span className={`wf-ico ${tone}`}>{icon}</span>
      </div>
      <div className="wf-kpi-num">{loading ? <Skel w={64} h={28} /> : value}</div>
      {progress != null && !loading && (
        <div className="wf-meter" role="progressbar" aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100}>
          <i className={tone} style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
        </div>
      )}
      <div className="wf-kpi-sub">
        {loading ? <Skel w={96} h={11} /> : (
          <>
            {trend && <span className={`wf-trend ${trend.tone}`}>{trend.text}</span>}
            <span>{sub}</span>
          </>
        )}
      </div>
    </div>
  );
}

export function OverviewItem({ icon, tone, label, sub, chip, chipTone, progress, loading, onOpen }: {
  icon: ReactNode;
  tone: Tone;
  label: string;
  sub: string;
  chip: string;
  chipTone: "ok" | "warn" | "crit";
  progress?: number | null;
  loading: boolean;
  onOpen: () => void;
}) {
  return (
    <div className="wf-ov">
      <span className={`wf-ico ${tone}`}>{icon}</span>
      <div className="wf-ov-main">
        <b>{label}</b>
        <small>{loading ? <Skel w={110} h={10} /> : sub}</small>
      </div>
      <div className="wf-ov-meter">
        {progress != null && !loading && (
          <div className="wf-meter" role="progressbar" aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100}>
            <i className={chipTone === "crit" ? "crit" : chipTone === "warn" ? "warn" : "ok"} style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
          </div>
        )}
      </div>
      {loading ? <Skel w={92} h={22} /> : <span className={`wf-chip ${chipTone}`}>{chip}</span>}
      <button type="button" className="wf-open" onClick={onOpen} aria-label={`Open ${label}`}>
        Open {WfIcon.chevron}
      </button>
    </div>
  );
}

export function QuickTile({ icon, tone, title, sub, onClick }: {
  icon: ReactNode; tone: Tone; title: string; sub: string; onClick: () => void;
}) {
  return (
    <button type="button" className="wf-qa" onClick={onClick}>
      <span className={`wf-ico ${tone}`}>{icon}</span>
      <span className="wf-qa-go">{WfIcon.chevron}</span>
      <span className="wf-qa-txt"><b>{title}</b><small>{sub}</small></span>
    </button>
  );
}

/**
 * Last-7-days attendance. Bar height = present ÷ headcount (attendance %), the
 * most recent day (today) is emphasised. Hover/focus a bar for the exact count.
 */
export function AttendanceTrend({ data, total, loading }: {
  data: { label: string; count: number }[]; total: number; loading: boolean;
}) {
  if (loading) {
    return <div className="wf-trend-chart wf-trend-empty"><Skel w="100%" h={120} /></div>;
  }
  if (!data.length) {
    return <div className="wf-trend-chart wf-trend-empty">No attendance recorded in the last 7 days.</div>;
  }
  const scale = total > 0 ? total : Math.max(1, ...data.map((d) => d.count));
  return (
    <div className="wf-trend-chart">
      <div className="wf-grid" aria-hidden="true">
        {[100, 75, 50, 25, 0].map((p) => <span key={p}><em>{p}%</em></span>)}
      </div>
      <div className="wf-cols">
        {data.map((d, i) => {
          const pct = Math.min(100, (d.count / scale) * 100);
          const today = i === data.length - 1;
          return (
            <div className="wf-col" key={i} tabIndex={0} title={`${d.count} present · ${Math.round(pct)}% of headcount`}>
              <span className="wf-col-val">{d.count}</span>
              <div className="wf-bar-wrap"><i className={today ? "today" : ""} style={{ height: `${Math.max(3, pct)}%` }} /></div>
              <span className={`wf-col-lbl${today ? " today" : ""}`}>{d.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Week-at-a-glance figures, all derived from the same weekly_attendance series. */
export function AttendanceInsights({ data, total, loading }: {
  data: { label: string; count: number }[]; total: number; loading: boolean;
}) {
  const counts = data.map((d) => d.count);
  const today = counts.length ? counts[counts.length - 1] : 0;
  const avg = counts.length ? Math.round(counts.reduce((a, b) => a + b, 0) / counts.length) : 0;
  const high = counts.length ? Math.max(...counts) : 0;
  const share = (n: number) => (total > 0 ? `${Math.round((n / total) * 100)}% of headcount` : "present");
  const rows: { label: string; value: number; note: string; tone: Tone }[] = [
    { label: "Today", value: today, note: share(today), tone: "brand" },
    { label: "7-day average", value: avg, note: `${share(avg)} per day`, tone: "info" },
    { label: "Highest day", value: high, note: share(high), tone: "ok" },
  ];
  return (
    <div className="wf-insights">
      {rows.map((r) => (
        <div className="wf-insight" key={r.label}>
          <span className={`wf-dot ${r.tone}`} aria-hidden="true" />
          <div>
            <small>{r.label}</small>
            <b>{loading ? <Skel w={40} h={20} /> : data.length ? r.value : "–"}</b>
            <em>{loading ? <Skel w={90} h={10} /> : data.length ? r.note : "No data yet"}</em>
          </div>
        </div>
      ))}
    </div>
  );
}
