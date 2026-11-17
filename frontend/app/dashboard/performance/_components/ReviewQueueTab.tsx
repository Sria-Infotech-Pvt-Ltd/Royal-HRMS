"use client";

import { useState } from "react";
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
  return (
    <ol className="perf-steps" aria-label="Progress">
      {STEPS.map(step => <li key={step.label} className={step.done(review) ? "done" : ""} title={`${step.label}: ${step.done(review) ? "done" : "not yet"}`} />)}
    </ol>
  );
}

/** Every review in the active cycle: search, filter by step, and act on each one. */
export default function ReviewQueueTab(props: ReviewQueueTabProps) {
  const { cycle, reviews, visible, today, isLoading, search, stage } = props;
  const [limit, setLimit] = useState(PAGE_SIZE);
  const counts = stageCounts(reviews);
  const hasFilters = hasActiveFilters(search, stage);
  const stageLabel = STAGES.find(item => item.key === stage)?.short ?? (stage === "needs_hr" ? "Needs HR" : "");
  const shown = visible.slice(0, limit);

  if (!isLoading && !cycle) {
    return <div className="card perf-start"><i className="ti ti-list-details perf-start-icon" /><h3>No active review cycle</h3><p>Activate a cycle from the Cycles tab to start the review queue.</p></div>;
  }

  return (
    <div className="perf-stack">
      <div className="card cand-toolbar">
        <div className="cand-toolbar-row">
          <div className="cand-search">
            <i className="ti ti-search" aria-hidden="true" />
            <input type="search" className="field-input" placeholder="Search by employee, code or manager" aria-label="Search reviews" value={search} maxLength={100}
              onChange={event => { props.onSearch(event.target.value); setLimit(PAGE_SIZE); }} suppressHydrationWarning />
            {search && <button type="button" className="cand-search-clear" aria-label="Clear search" onClick={() => props.onSearch("")}><i className="ti ti-x" /></button>}
          </div>
          <label className="cand-select">
            <i className="ti ti-filter" aria-hidden="true" />
            <span className="sr-only">Step</span>
            <select className="field-input field-select" value={stage} onChange={event => { props.onStage(event.target.value as StageFilter); setLimit(PAGE_SIZE); }} suppressHydrationWarning>
              <option value="">All steps ({counts.total})</option>
              <option value="needs_hr">Needs HR ({counts.awaiting_calibration + counts.awaiting_publish})</option>
              {STAGES.map(item => <option key={item.key} value={item.key}>{item.short} ({counts[item.key]})</option>)}
            </select>
          </label>
        </div>
        {hasFilters && (
          <div className="cand-chips" aria-label="Active filters">
            <span className="cand-chips-label" role="status">Showing {visible.length} of {counts.total}</span>
            {search.trim() && <span className="cand-chip">“{search.trim()}”<button type="button" aria-label="Remove search filter" onClick={() => props.onSearch("")}><i className="ti ti-x" aria-hidden="true" /></button></span>}
            {stage && <span className="cand-chip">{stageLabel}<button type="button" aria-label="Remove step filter" onClick={() => props.onStage("")}><i className="ti ti-x" aria-hidden="true" /></button></span>}
            <button type="button" className="btn-link" onClick={props.onClear}>Clear all</button>
          </div>
        )}
      </div>

      <div className="card">
        {isLoading ? (
          <div className="cand-skeleton" role="status" aria-label="Loading reviews">{[0, 1, 2, 3].map(row => <div key={row} className="cand-skeleton-row"><span className="cand-skeleton-dot" /><span className="cand-skeleton-bar" /></div>)}</div>
        ) : visible.length === 0 ? (
          <div className="empty-state cand-empty">
            <i className={`ti ${hasFilters ? "ti-search-off" : "ti-list-details"}`} />
            <h3>{hasFilters ? "No reviews match your filters" : "No employee reviews yet"}</h3>
            <p>{hasFilters ? "Try a different search or step, or clear the filters." : "Reviews appear here once an employee opens their Appraisals tab."}</p>
            {hasFilters && <button type="button" className="btn btn-ghost" onClick={props.onClear}><i className="ti ti-filter-off" /> Clear filters</button>}
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Employee</th><th>Manager</th><th>Progress</th><th>Step</th><th>Action</th></tr></thead>
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
                        <span className={`badge badge-${meta?.tone ?? "neutral"}`}>{meta?.short}</span>
                        {isOverdue && <span className="badge badge-error perf-overdue">Overdue</span>}
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
            <span>Showing {shown.length} of {visible.length}</span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setLimit(value => value + PAGE_SIZE)}>Show more</button>
          </div>
        )}
      </div>
    </div>
  );
}
