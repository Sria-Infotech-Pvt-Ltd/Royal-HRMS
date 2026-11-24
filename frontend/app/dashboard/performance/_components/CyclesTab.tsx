"use client";

import { useT } from "@/hooks/useI18n";
import { formatDate } from "@/lib/formatDate";
import { cycleProgress, relativeDay } from "@/lib/performanceHub";
import type { ApiCycle } from "@/types/performanceHub";

interface CyclesTabProps {
  cycles:     ApiCycle[]
  today:      Date
  isLoading:  boolean
  busyId:     string | null
  error:      string
  onDismissError: () => void
  onCreate:   () => void
  onActivate: (id: string) => void
  onClose:    (id: string) => void
}

const BADGE = { draft: "badge-neutral", active: "badge-success", closed: "badge-neutral" } as const;
const ORDER = { active: 0, draft: 1, closed: 2 } as const;

function CycleCard({ cycle, today, busy, onActivate, onClose }: { cycle: ApiCycle; today: Date; busy: boolean; onActivate: () => void; onClose: () => void }) {
  const t = useT();
  const progress = cycleProgress(cycle, today);
  return (
    <article className={`card perf-cycle${cycle.status === "active" ? " is-active" : ""}`}>
      <header>
        <div>
          <h3>{cycle.name}</h3>
          <span className="perf-muted">{t("{start} to {end}", { start: formatDate(cycle.period_start), end: formatDate(cycle.period_end) })}</span>
        </div>
        <span className={`badge ${BADGE[cycle.status]}`}>{cycle.status === "draft" ? t("Draft") : cycle.status === "active" ? t("Active") : t("Closed")}</span>
      </header>

      {progress && cycle.status !== "draft" && (
        <div className="perf-track slim" role="img" aria-label={t("{percent}% of the period has passed", { percent: Math.round(progress.percent) })}>
          <span className="perf-track-fill" style={{ width: `${cycle.status === "closed" ? 100 : progress.percent}%` }} />
        </div>
      )}

      <dl className="perf-dates">
        <div><dt>{t("Self reviews due")}</dt><dd>{formatDate(cycle.self_review_due)} <span>{cycle.status === "closed" ? "" : relativeDay(cycle.self_review_due, today)}</span></dd></div>
        <div><dt>{t("Manager reviews due")}</dt><dd>{formatDate(cycle.manager_review_due)} <span>{cycle.status === "closed" ? "" : relativeDay(cycle.manager_review_due, today)}</span></dd></div>
      </dl>

      <footer>
        {cycle.status === "draft" && <button type="button" className="btn btn-filled btn-sm" onClick={onActivate} disabled={busy}>{busy ? t("Activating…") : <><i className="ti ti-player-play" /> {t("Activate")}</>}</button>}
        {cycle.status === "active" && <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>{busy ? t("Closing…") : <><i className="ti ti-lock" /> {t("Close cycle")}</>}</button>}
        {cycle.status === "closed" && <span className="perf-muted"><i className="ti ti-lock" /> {t("Closed cycles cannot be reopened.")}</span>}
      </footer>
    </article>
  );
}

/** Every review cycle, newest purpose first: the active one, then drafts, then closed ones. */
export default function CyclesTab(props: CyclesTabProps) {
  const t = useT();
  const sorted = [...props.cycles].sort((first, second) => ORDER[first.status] - ORDER[second.status] || second.period_start.localeCompare(first.period_start));
  return (
    <div className="perf-stack">
      {props.error && (
        <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{props.error}</div>
          <button type="button" className="btn-link" style={{ marginLeft: "auto" }} onClick={props.onDismissError}>{t("Dismiss")}</button>
        </div>
      )}
      {props.isLoading && sorted.length === 0 ? (
        <div className="perf-cycles">{[0, 1].map(row => <div key={row} className="asm-skeleton" />)}</div>
      ) : sorted.length === 0 ? (
        <div className="card perf-start">
          <i className="ti ti-calendar-time perf-start-icon" /><h3>{t("No review cycles yet")}</h3>
          <p>{t("A cycle sets the period, the self-review deadline and the manager-review deadline.")}</p>
          <button type="button" className="btn btn-filled" onClick={props.onCreate}><i className="ti ti-plus" /> {t("New review cycle")}</button>
        </div>
      ) : (
        <div className="perf-cycles">
          {sorted.map(cycle => (
            <CycleCard key={cycle.id} cycle={cycle} today={props.today} busy={props.busyId === cycle.id}
              onActivate={() => props.onActivate(cycle.id)} onClose={() => props.onClose(cycle.id)} />
          ))}
          <button type="button" className="asm-new-tile perf-new-cycle" onClick={props.onCreate}>
            <span className="asm-new-text"><strong><i className="ti ti-plus" /> {t("New review cycle")}</strong><span>{t("Only one cycle can be active at a time.")}</span></span>
          </button>
        </div>
      )}
    </div>
  );
}
