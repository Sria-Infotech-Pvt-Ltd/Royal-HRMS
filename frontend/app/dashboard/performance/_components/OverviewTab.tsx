"use client";

import Link from "next/link";
import { formatDate } from "@/lib/formatDate";
import { personInitials } from "@/lib/faceRegistrationStatus";
import { cycleProgress, isSelfReviewOverdue, needsHr, percentOf, reviewStage, stageCounts, type StageFilter } from "@/lib/performanceHub";
import type { ApiCycle, ApiReview, HrQueueData } from "@/types/performanceHub";
import CycleTimeline from "./CycleTimeline";
import StageFunnel from "./StageFunnel";
import ReviewQueueRowActions from "./ReviewQueueRowActions";

interface OverviewTabProps {
  data:       HrQueueData | null
  cycles:     ApiCycle[]
  today:      Date
  isLoading:  boolean
  busyId:     string | null
  onOpenQueue: (stage: StageFilter) => void
  onOpenCycles: () => void
  onCreate:   () => void
  onActivate: (id: string) => void
  onReview:   (review: ApiReview) => void
  onChanged:  () => void
}

const MY_LINKS = [
  { href: "/dashboard/ess?tab=growth",     icon: "ti-target-arrow",  title: "My goals and feedback", text: "Set your own goals and ask for feedback." },
  { href: "/dashboard/ess?tab=appraisals", icon: "ti-file-certificate", title: "My appraisal",        text: "Write your self review and see your outcome." },
];

function StatCards({ data, onOpenQueue, onOpenCycles, today }: Pick<OverviewTabProps, "data" | "onOpenQueue" | "onOpenCycles" | "today">) {
  const cycle = data?.cycle ?? null;
  const counts = stageCounts(data?.reviews ?? []);
  const selfDone = counts.total - counts.not_started;
  const managerDone = counts.total - counts.not_started - counts.awaiting_manager;
  const daysLeft = cycle ? cycleProgress(cycle, today)?.daysLeft ?? 0 : 0;
  const cards = [
    { label: "Active cycle", value: cycle?.name ?? "None", sub: cycle ? `${daysLeft} day${daysLeft === 1 ? "" : "s"} left` : "Create and activate one", icon: "ti-calendar-time", tone: "si-primary", onClick: onOpenCycles },
    { label: "Self reviews", value: `${selfDone} / ${counts.total}`, sub: `${percentOf(selfDone, counts.total)}% submitted`, icon: "ti-user-edit", tone: "si-info", onClick: () => onOpenQueue("not_started") },
    { label: "Manager reviews", value: `${managerDone} / ${counts.total}`, sub: `${percentOf(managerDone, counts.total)}% done`, icon: "ti-user-check", tone: "si-success", onClick: () => onOpenQueue("awaiting_manager") },
    { label: "Goals at risk", value: String(data?.stats?.goals_at_risk ?? 0), sub: "Needs follow-up", icon: "ti-alert-triangle", tone: "si-error", onClick: null },
  ];
  return (
    <div className="stats-grid">
      {cards.map(card => {
        const body = (
          <>
            <div className={`stat-icon ${card.tone}`}><i className={`ti ${card.icon}`} /></div>
            <div className="stat-label">{card.label}</div>
            <div className="stat-value perf-stat-value">{card.value}</div>
            <div className="stat-sub">{card.sub}</div>
          </>
        );
        return card.onClick
          ? <button key={card.label} type="button" className="stat-card cand-stat" onClick={card.onClick}>{body}</button>
          : <div key={card.label} className="stat-card">{body}</div>;
      })}
    </div>
  );
}

function Attention({ reviews, cycle, today, onReview, onChanged }: { reviews: ApiReview[]; cycle: ApiCycle | null; today: Date; onReview: (review: ApiReview) => void; onChanged: () => void }) {
  const rows = reviews.filter(review => needsHr(reviewStage(review)) || isSelfReviewOverdue(review, cycle, today)).slice(0, 6);
  if (rows.length === 0) {
    return <div className="perf-allclear"><i className="ti ti-circle-check" /> Nothing needs your attention right now.</div>;
  }
  return (
    <ul className="perf-attention">
      {rows.map(review => {
        const stage = reviewStage(review);
        const reason = stage === "awaiting_calibration" ? "Ready to calibrate" : stage === "awaiting_publish" ? "Ready to publish" : "Self review overdue";
        return (
          <li key={review.id}>
            <span className="fid-avatar" aria-hidden="true">{personInitials(review.employee_name)}</span>
            <span className="perf-attention-text"><strong>{review.employee_name}</strong><span>{review.employee_code} · {reason}</span></span>
            <ReviewQueueRowActions review={review} onReview={onReview} onChanged={onChanged} />
          </li>
        );
      })}
    </ul>
  );
}

/** The first thing HR sees: headline numbers, the cycle's timeline, where every review is, and what needs doing now. */
export default function OverviewTab(props: OverviewTabProps) {
  const { data, cycles, today, isLoading } = props;
  const cycle = data?.cycle ?? null;
  const counts = stageCounts(data?.reviews ?? []);
  const drafts = cycles.filter(item => item.status === "draft");

  return (
    <div className="perf-stack">
      <StatCards data={data} onOpenQueue={props.onOpenQueue} onOpenCycles={props.onOpenCycles} today={today} />

      {!cycle && !isLoading ? (
        <div className="card perf-start">
          <i className="ti ti-calendar-plus perf-start-icon" />
          <h3>No review cycle is running</h3>
          <p>{drafts.length > 0 ? "Activate one of your drafts, or create a new cycle." : "Create a cycle to start collecting self reviews and manager reviews."}</p>
          {drafts.length > 0 && (
            <ul className="perf-drafts">
              {drafts.map(draft => (
                <li key={draft.id}>
                  <span><strong>{draft.name}</strong> · {formatDate(draft.period_start)} to {formatDate(draft.period_end)}</span>
                  <button type="button" className="btn btn-filled btn-sm" disabled={props.busyId === draft.id} onClick={() => props.onActivate(draft.id)}>
                    {props.busyId === draft.id ? "Activating…" : "Activate"}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button type="button" className="btn btn-filled" onClick={props.onCreate}><i className="ti ti-plus" /> New review cycle</button>
        </div>
      ) : (
        <div className="perf-grid">
          <section className="card perf-card">
            <header><h3><i className="ti ti-timeline" /> {cycle ? cycle.name : "Cycle"} timeline</h3></header>
            {cycle ? <CycleTimeline cycle={cycle} today={today} /> : <p className="perf-muted">Loading…</p>}
          </section>
          <section className="card perf-card">
            <header><h3><i className="ti ti-filter" /> Where every review is</h3><span className="perf-muted">{counts.total} total</span></header>
            <StageFunnel counts={counts} onSelect={stage => props.onOpenQueue(stage)} />
          </section>
          <section className="card perf-card">
            <header>
              <h3><i className="ti ti-bell-ringing" /> Needs your attention</h3>
              <button type="button" className="btn-link" onClick={() => props.onOpenQueue("needs_hr")}>See all</button>
            </header>
            <Attention reviews={data?.reviews ?? []} cycle={cycle} today={today} onReview={props.onReview} onChanged={props.onChanged} />
          </section>
          <section className="card perf-card">
            <header><h3><i className="ti ti-bolt" /> Quick actions</h3></header>
            <div className="perf-quick">
              <button type="button" className="perf-quick-tile" onClick={props.onCreate}><i className="ti ti-plus" /><strong>New review cycle</strong><span>Set the period and due dates.</span></button>
              <button type="button" className="perf-quick-tile" onClick={props.onOpenCycles}><i className="ti ti-calendar-time" /><strong>Manage cycles</strong><span>Activate, close and review past cycles.</span></button>
              {MY_LINKS.map(link => (
                <Link key={link.href} className="perf-quick-tile" href={link.href}><i className={`ti ${link.icon}`} /><strong>{link.title}</strong><span>{link.text}</span></Link>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
