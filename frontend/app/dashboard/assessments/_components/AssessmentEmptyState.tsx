"use client";

import type { AssessmentTemplate } from "@/lib/assessmentTemplates";
import AssessmentTemplatePicker from "./AssessmentTemplatePicker";
import { useT } from "@/hooks/useI18n";

interface AssessmentEmptyStateProps {
  /** True when assessments exist but the search / filter hides them all. */
  isFiltered: boolean
  canCreate:  boolean
  onCreate:   (template: AssessmentTemplate) => void
  onClear:    () => void
}

const STEPS = ["Pick a type", "Add videos and questions in Sections", "Assign it and follow the results"];

/** Nothing to show: either no matches for the filters, or a first-time start with the assessment types to choose from. */
export default function AssessmentEmptyState({ isFiltered, canCreate, onCreate, onClear }: AssessmentEmptyStateProps) {
  const t = useT();
  if (isFiltered) {
    return (
      <div className="card asm-empty">
        <i className="ti ti-search-off asm-empty-icon" />
        <h3>{t("No assessments match your filters")}</h3>
        <p>{t("Try a different search, or clear the filters to see every assessment.")}</p>
        <button type="button" className="btn btn-ghost" onClick={onClear}><i className="ti ti-filter-off" /> {t("Clear filters")}</button>
      </div>
    );
  }
  return (
    <div className="card asm-empty">
      <i className="ti ti-clipboard-list asm-empty-icon" />
      <h3>{canCreate ? t("Create your first assessment") : t("No assessments yet")}</h3>
      <p>
        {canCreate
          ? t("Assessments check that new joiners have understood the material before they start. Choose a type to begin.")
          : t("Assessments will appear here once someone with access creates them.")}
      </p>
      {canCreate && <AssessmentTemplatePicker variant="cards" onPick={onCreate} />}
      {canCreate && (
        <ol className="asm-flow" aria-label={t("How it works")}>
          {STEPS.map((step, index) => <li key={step}><span>{index + 1}</span>{t(step)}</li>)}
        </ol>
      )}
    </div>
  );
}
