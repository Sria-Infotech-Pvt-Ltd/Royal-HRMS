"use client";

import type { ReactNode } from "react";
import { attemptsLabel, completionPercent, progressParts, timeLimitLabel } from "@/lib/assessmentFilters";
import type { Assessment } from "../_types";
import { useT } from "@/hooks/useI18n";

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
  const t = useT();
  if (assessment.assigned_count <= 0) {
    return <div className="asm-progress-empty"><i className="ti ti-user-plus" /> {t("Not assigned to anyone yet")}</div>;
  }
  const parts = progressParts(assessment);
  const percent = completionPercent(assessment);
  return (
    <div className="asm-progress">
      <div className="asm-progress-top">
        <span><strong>{assessment.assigned_count}</strong> {t("assigned")}</span>
        <span className="asm-progress-percent">{t("{percent}% complete", { percent })}</span>
      </div>
      <div className="asm-bar" role="img" aria-label={t("{percent}% complete: {done} done, {doing} in progress, {todo} not started", { percent, done: assessment.completed_count, doing: assessment.in_progress_count, todo: assessment.pending_count })}>
        <span className="asm-bar-done" style={{ width: `${parts.completed}%` }} />
        <span className="asm-bar-doing" style={{ width: `${parts.inProgress}%` }} />
        <span className="asm-bar-todo" style={{ width: `${parts.pending}%` }} />
      </div>
      <div className="asm-legend">
        <span><i className="asm-dot done" /> {t("{count} completed", { count: assessment.completed_count })}</span>
        <span><i className="asm-dot doing" /> {t("{count} in progress", { count: assessment.in_progress_count })}</span>
        <span><i className="asm-dot todo" /> {t("{count} not started", { count: assessment.pending_count })}</span>
      </div>
    </div>
  );
}

/** One assessment: what it is, its rules, how far along the people assigned to it are, and what you can do with it. */
export default function AssessmentCard(props: AssessmentCardProps) {
  const t = useT();
  const { assessment: a, canEdit, canDelete, isExpanded } = props;
  return (
    <article className={`asm-card${a.is_active ? "" : " is-inactive"}`}>
      <div className="asm-card-head">
        <div className="asm-icon" aria-hidden="true"><i className="ti ti-clipboard-check" /></div>
        <div className="asm-main">
          <div className="asm-title-row">
            <h3 className="asm-title">{a.title}</h3>
            <span className={`badge ${a.is_active ? "badge-success" : "badge-neutral"}`}>{a.is_active ? t("Active") : t("Inactive")}</span>
          </div>
          {a.description && <p className="asm-desc">{a.description}</p>}
          <div className="asm-chips">
            <span className="asm-chip"><i className="ti ti-layout-list" /> {a.item_count === 1 ? t("{count} item", { count: a.item_count }) : t("{count} items", { count: a.item_count })}</span>
            <span className="asm-chip"><i className="ti ti-target" /> {t("{percent}% to pass", { percent: a.pass_percentage })}</span>
            <span className="asm-chip"><i className="ti ti-refresh" /> {attemptsLabel(a)}</span>
            <span className="asm-chip"><i className="ti ti-clock" /> {timeLimitLabel(a)}</span>
          </div>
        </div>
        <div className="asm-actions">
          {canEdit && (
            <button type="button" className="btn btn-filled btn-sm" onClick={props.onAssign}><i className="ti ti-user-plus" /> {t("Assign")}</button>
          )}
          {canEdit && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={props.onSections}><i className="ti ti-layout-list" /> {t("Sections")}</button>
          )}
          {canEdit && (
            <button type="button" className="btn btn-ghost btn-sm cand-icon-btn" title={t("Edit assessment")} aria-label={t("Edit {title}", { title: a.title })} onClick={props.onEdit}><i className="ti ti-pencil" /></button>
          )}
          {canDelete && (
            <button type="button" className="btn btn-ghost btn-sm cand-icon-btn" style={{ color: "var(--error)" }} title={t("Delete assessment")} aria-label={t("Delete {title}", { title: a.title })} onClick={props.onDelete}><i className="ti ti-trash" /></button>
          )}
        </div>
      </div>

      <div className="asm-card-foot">
        <Progress assessment={a} />
        <button type="button" className="btn btn-ghost btn-sm" aria-expanded={isExpanded} onClick={props.onToggleResults}>
          <i className={`ti ${isExpanded ? "ti-chevron-up" : "ti-chart-bar"}`} /> {isExpanded ? t("Hide results") : t("View results")}
        </button>
      </div>

      {isExpanded && <div className="asm-results">{props.children}</div>}
    </article>
  );
}
