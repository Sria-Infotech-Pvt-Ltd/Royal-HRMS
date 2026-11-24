"use client";

import { ASSESSMENT_TEMPLATES, type AssessmentTemplate } from "@/lib/assessmentTemplates";

import { useT } from "@/hooks/useI18n";

interface AssessmentTemplatePickerProps {
  /** "cards": large, for an empty page. "compact": one slim row, for under an existing list. */
  variant:  "cards" | "compact"
  onPick:   (template: AssessmentTemplate) => void
}

/** The ways to start a new assessment: a quiz, video training, both, or from scratch. */
export default function AssessmentTemplatePicker({ variant, onPick }: AssessmentTemplatePickerProps) {
  const t = useT();
  if (variant === "compact") {
    return (
      <div className="asm-new-tile">
        <div className="asm-new-text">
          <strong><i className="ti ti-plus" /> {t("Create a new assessment")}</strong>
          <span>{t("Pick a type to start from")}</span>
        </div>
        <div className="asm-new-buttons">
          {ASSESSMENT_TEMPLATES.map(template => (
            <button key={template.id} type="button" className="btn btn-ghost btn-sm" onClick={() => onPick(template)}>
              <i className={`ti ${template.icon}`} /> {t(template.title)}
            </button>
          ))}
        </div>
      </div>
    );
  }
  return (
    <ul className="asm-types" aria-label={t("Assessment types")}>
      {ASSESSMENT_TEMPLATES.map(template => (
        <li key={template.id}>
          <button type="button" className={`asm-type tone-${template.tone}`} onClick={() => onPick(template)}>
            <span className="asm-type-icon"><i className={`ti ${template.icon}`} /></span>
            <strong>{t(template.title)}</strong>
            <span className="asm-type-summary">{t(template.summary)}</span>
            <span className="asm-type-contains"><i className="ti ti-layout-list" /> {t(template.contains)}</span>
            <span className="asm-type-go">{t("Use this")} <i className="ti ti-arrow-right" /></span>
          </button>
        </li>
      ))}
    </ul>
  );
}
