"use client";

import type { ReactNode } from "react";
import { attemptsLabel, completionPercent, progressParts, timeLimitLabel } from "@/lib/assessmentFilters";
import type { Assessment } from "../_types";

interface AssessmentCardProps {
  assessment:      Assessment
  canEdit:         boolean
  canDelete:       boolean
  isExpanded:      boolean
  onToggleResults: () => void
  onSections:      () => void
  onAssign:        () => void
  onEdit:          () => void
  onDelete:        () => void
  /** The results panel, shown under the card when it is expanded. */
  children?:       ReactNode
}

function Progress({ assessment }: { assessment: Assessment }) {
  if (assessment.assigned_count <= 0) {
    return <div className="asm-progress-empty"><i className="ti ti-user-plus" /> Not assigned to anyone yet</div>;
  }
  const parts = progressParts(assessment);
  const percent = completionPercent(assessment);
  return (
    <div className="asm-progress">
      <div className="asm-progress-top">
        <span><strong>{assessment.assigned_count}</strong> assigned</span>
        <span className="asm-progress-percent">{percent}% complete</span>
      </div>
      <div className="asm-bar" role="img" aria-label={`${percent}% complete: ${assessment.completed_count} done, ${assessment.in_progress_count} in progress, ${assessment.pending_count} not started`}>
        <span className="asm-bar-done" style={{ width: `${parts.completed}%` }} />
        <span className="asm-bar-doing" style={{ width: `${parts.inProgress}%` }} />
        <span className="asm-bar-todo" style={{ width: `${parts.pending}%` }} />
      </div>
      <div className="asm-legend">
        <span><i className="asm-dot done" /> {assessment.completed_count} completed</span>
        <span><i className="asm-dot doing" /> {assessment.in_progress_count} in progress</span>
        <span><i className="asm-dot todo" /> {assessment.pending_count} not started</span>
      </div>
    </div>
  );
}

/** One assessment: what it is, its rules, how far along the people assigned to it are, and what you can do with it. */
export default function AssessmentCard(props: AssessmentCardProps) {
  const { assessment: a, canEdit, canDelete, isExpanded } = props;
  return (
    <article className={`asm-card${a.is_active ? "" : " is-inactive"}`}>
      <div className="asm-card-head">
        <div className="asm-icon" aria-hidden="true"><i className="ti ti-clipboard-check" /></div>
        <div className="asm-main">
          <div className="asm-title-row">
            <h3 className="asm-title">{a.title}</h3>
            <span className={`badge ${a.is_active ? "badge-success" : "badge-neutral"}`}>{a.is_active ? "Active" : "Inactive"}</span>
          </div>
          {a.description && <p className="asm-desc">{a.description}</p>}
          <div className="asm-chips">
            <span className="asm-chip"><i className="ti ti-layout-list" /> {a.item_count} {a.item_count === 1 ? "item" : "items"}</span>
            <span className="asm-chip"><i className="ti ti-target" /> {a.pass_percentage}% to pass</span>
            <span className="asm-chip"><i className="ti ti-refresh" /> {attemptsLabel(a)}</span>
            <span className="asm-chip"><i className="ti ti-clock" /> {timeLimitLabel(a)}</span>
          </div>
        </div>
        <div className="asm-actions">
          {canEdit && (
            <button type="button" className="btn btn-filled btn-sm" onClick={props.onAssign}><i className="ti ti-user-plus" /> Assign</button>
          )}
          {canEdit && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={props.onSections}><i className="ti ti-layout-list" /> Sections</button>
          )}
          {canEdit && (
            <button type="button" className="btn btn-ghost btn-sm cand-icon-btn" title="Edit assessment" aria-label={`Edit ${a.title}`} onClick={props.onEdit}><i className="ti ti-pencil" /></button>
          )}
          {canDelete && (
            <button type="button" className="btn btn-ghost btn-sm cand-icon-btn" style={{ color: "var(--error)" }} title="Delete assessment" aria-label={`Delete ${a.title}`} onClick={props.onDelete}><i className="ti ti-trash" /></button>
          )}
        </div>
      </div>

      <div className="asm-card-foot">
        <Progress assessment={a} />
        <button type="button" className="btn btn-ghost btn-sm" aria-expanded={isExpanded} onClick={props.onToggleResults}>
          <i className={`ti ${isExpanded ? "ti-chevron-up" : "ti-chart-bar"}`} /> {isExpanded ? "Hide results" : "View results"}
        </button>
      </div>

      {isExpanded && <div className="asm-results">{props.children}</div>}
    </article>
  );
}
