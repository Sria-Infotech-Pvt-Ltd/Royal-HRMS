"use client";

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import { personInitials } from "@/lib/faceRegistrationStatus";
import { STAGES, hasActiveFilters, isSelfReviewOverdue, reviewStage, stageCounts, type StageFilter } from "@/lib/performanceHub";
import type { ApiCycle, ApiReview } from "@/types/performanceHub";
import ReviewQueueRowActions from "./ReviewQueueRowActions";

interface ReviewQueueTabProps {
  cycle:     ApiCycle | null
  reviews:   ApiReview[]
  /** The reviews left after the search and the step filter. */
  visible:   ApiReview[]
  today:     Date
  isLoading: boolean
  search:    string
  onSearch:  (text: string) => void
  stage:     StageFilter
  onStage:   (stage: StageFilter) => void
  onClear:   () => void
  onReview:  (review: ApiReview) => void
  onChanged: () => void
}

const PAGE_SIZE = 25;
const STEPS = [
  { label: "Self review", done: (review: ApiReview) => !!review.self_submitted_at },
  { label: "Manager",     done: (review: ApiReview) => !!review.manager_submitted_at },
  { label: "Calibrated",  done: (review: ApiReview) => !!review.hr_calibrated_at },
  { label: "Published",   done: (review: ApiReview) => !!review.published_at },
];

function Stepper({ review }: { review: ApiReview }) {
  const t = useT();
  return (
    <ol className="perf-steps" aria-label={t("Progress")}>
      {STEPS.map(step => <li key={step.label} className={step.done(review) ? "done" : ""} title={t("{step}: {state}", { step: t(step.label), state: step.done(review) ? t("done") : t("not yet") })} />)}
    </ol>
  );
}

/** Every review in the active cycle: search, filter by step, and act on each one. */
export default function ReviewQueueTab(props: ReviewQueueTabProps) {
  const t = useT();
  const { cycle, reviews, visible, today, isLoading, search, stage } = props;
  const [limit, setLimit] = useState(PAGE_SIZE);
  const counts = stageCounts(reviews);
  const hasFilters = hasActiveFilters(search, stage);
  const stageShort = STAGES.find(item => item.key === stage)?.short;
  const stageLabel = stageShort ? t(stageShort) : stage === "needs_hr" ? t("Needs HR") : "";
  const shown = visible.slice(0, limit);

  if (!isLoading && !cycle) {
    return <div className="card perf-start"><i className="ti ti-list-details perf-start-icon" /><h3>{t("No active review cycle")}</h3><p>{t("Activate a cycle from the Cycles tab to start the review queue.")}</p></div>;
  }

  return (
    <div className="perf-stack">
      <div className="card cand-toolbar">
        <div className="cand-toolbar-row">
          <div className="cand-search">
            <i className="ti ti-search" aria-hidden="true" />
            <input type="search" className="field-input" placeholder={t("Search by employee, code or manager")} aria-label={t("Search reviews")} value={search} maxLength={100}
              onChange={event => { props.onSearch(event.target.value); setLimit(PAGE_SIZE); }} suppressHydrationWarning />
            {search && <button type="button" className="cand-search-clear" aria-label={t("Clear search")} onClick={() => props.onSearch("")}><i className="ti ti-x" /></button>}
          </div>
          <label className="cand-select">
            <i className="ti ti-filter" aria-hidden="true" />
            <span className="sr-only">{t("Step")}</span>
            <select className="field-input field-select" value={stage} onChange={event => { props.onStage(event.target.value as StageFilter); setLimit(PAGE_SIZE); }} suppressHydrationWarning>
              <option value="">{t("All steps ({count})", { count: counts.total })}</option>
              <option value="needs_hr">{t("Needs HR ({count})", { count: counts.awaiting_calibration + counts.awaiting_publish })}</option>
              {STAGES.map(item => <option key={item.key} value={item.key}>{t("{step} ({count})", { step: t(item.short), count: counts[item.key] })}</option>)}
            </select>
          </label>
        </div>
        {hasFilters && (
          <div className="cand-chips" aria-label={t("Active filters")}>
            <span className="cand-chips-label" role="status">{t("Showing {shown} of {total}", { shown: visible.length, total: counts.total })}</span>
            {search.trim() && <span className="cand-chip">“{search.trim()}”<button type="button" aria-label={t("Remove search filter")} onClick={() => props.onSearch("")}><i className="ti ti-x" aria-hidden="true" /></button></span>}
            {stage && <span className="cand-chip">{stageLabel}<button type="button" aria-label={t("Remove step filter")} onClick={() => props.onStage("")}><i className="ti ti-x" aria-hidden="true" /></button></span>}
            <button type="button" className="btn-link" onClick={props.onClear}>{t("Clear all")}</button>
          </div>
        )}
      </div>

      <div className="card">
        {isLoading ? (
          <div className="cand-skeleton" role="status" aria-label={t("Loading reviews")}>{[0, 1, 2, 3].map(row => <div key={row} className="cand-skeleton-row"><span className="cand-skeleton-dot" /><span className="cand-skeleton-bar" /></div>)}</div>
        ) : visible.length === 0 ? (
          <div className="empty-state cand-empty">
            <i className={`ti ${hasFilters ? "ti-search-off" : "ti-list-details"}`} />
            <h3>{hasFilters ? t("No reviews match your filters") : t("No employee reviews yet")}</h3>
            <p>{hasFilters ? t("Try a different search or step, or clear the filters.") : t("Reviews appear here once an employee opens their Appraisals tab.")}</p>
            {hasFilters && <button type="button" className="btn btn-ghost" onClick={props.onClear}><i className="ti ti-filter-off" /> {t("Clear filters")}</button>}
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>{t("Employee")}</th><th>{t("Manager")}</th><th>{t("Progress")}</th><th>{t("Step")}</th><th>{t("Action")}</th></tr></thead>
              <tbody>
                {shown.map(review => {
                  const meta = STAGES.find(item => item.key === reviewStage(review));
                  const isOverdue = isSelfReviewOverdue(review, cycle, today);
                  return (
                    <tr key={review.id}>
                      <td>
                        <div className="cand-person">
                          <span className="fid-avatar" aria-hidden="true">{personInitials(review.employee_name)}</span>
                          <div className="cand-person-text"><strong>{review.employee_name}</strong><span>{review.employee_code}</span></div>
                        </div>
                      </td>
                      <td>{review.manager_name || "—"}</td>
                      <td><Stepper review={review} /></td>
                      <td>
                        <span className={`badge badge-${meta?.tone ?? "neutral"}`}>{meta ? t(meta.short) : ""}</span>
                        {isOverdue && <span className="badge badge-error perf-overdue">{t("Overdue")}</span>}
                      </td>
                      <td><ReviewQueueRowActions review={review} onReview={props.onReview} onChanged={props.onChanged} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {visible.length > limit && (
          <div className="cand-pager">
            <span>{t("Showing {shown} of {total}", { shown: shown.length, total: visible.length })}</span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setLimit(value => value + PAGE_SIZE)}>{t("Show more")}</button>
          </div>
        )}
      </div>
    </div>
  );
}
