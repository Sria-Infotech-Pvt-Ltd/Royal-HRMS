"use client";

import { useT } from "@/hooks/useI18n";
export type HireStepTagTone = "sensitive" | "info" | "new";

export interface HireStepTag {
  label: string;
  tone: HireStepTagTone;
}

export interface HireStepDef {
  label: string;
  sub: string;
  required?: number;
  tag?: HireStepTag; // e.g. SENSITIVE / EPFO / NEW pill next to the title
  group?: string; // renders a section-group header ABOVE this step
}

interface Props {
  steps: HireStepDef[];
  currentStep: number;
  highestSaved: number;
  onStepClick: (index: number) => void;
  /** Overall progress of the hire, shown at the top of the rail. */
  progressPct?: number;
  missingByStep: Record<number, string[]>; // step index -> field labels still missing
}

// Left rail matching the reference mockup exactly: numbered circles (green
// check once passed, purple while active), a "RECORDS & COMPLIANCE" group
// header before step 5, and a running "N fields still required" box listing
// the first couple of incomplete steps' missing fields.
//
// Every step is always clickable — free-jump, like the HR-onboarding
// wizard's own StepIndicator (app/onboarding/_components/StepIndicator.tsx
// is the one that locks steps until the previous one is saved; this sidebar
// deliberately does NOT mirror that anymore, since HR filling this out
// needs to be able to jump ahead — e.g. to Documents or Review — without
// being forced through every step in order first).
export default function HireWizardSidebar({ steps, currentStep, highestSaved, onStepClick, missingByStep, progressPct }: Props) {
  const t = useT();
  const totalMissing = Object.values(missingByStep).reduce((n, arr) => n + arr.length, 0);

  return (
    <div className="wiz-nav">
      {progressPct !== undefined && (
        <div className="hw-rail-progress">
          <div><strong>{progressPct}%</strong> {t("of the hire is ready")}</div>
          <div className="hw-progress-bar"><span style={{ width: `${progressPct}%` }} /></div>
        </div>
      )}
      {steps.map((step, i) => {
        // For any step HireWizardClient actually tracks required fields for
        // (missingByStep[i] exists), the green check is re-derived from
        // CURRENT field values every render — never a one-time "you passed
        // Next through here once" flag. That used to mean a step validated
        // and passed, then edited back to blank afterward (e.g. clearing
        // PAN/Aadhaar after initially filling them), kept showing done
        // forever and inflating the progress % — the exact bug this fixes.
        // Untracked steps (Basic Pay, Assets — genuinely no required
        // fields) fall back to the historical highestSaved flag.
        const isDone = missingByStep[i] !== undefined
          ? missingByStep[i].length === 0
          : i <= highestSaved;
        // The little count pill next to a step's label used to be a static
        // number from STEPS[i].required that never changed regardless of
        // what was actually filled in (QA report #36 — "Personal stays 7
        // after filling"). For any step this component tracks live missing
        // fields for, show that real count instead; untracked steps
        // (Basic Pay, Assets) keep the original static hint.
        const requiredBadge = missingByStep[i] !== undefined ? missingByStep[i].length : step.required;
        const isActive    = i === currentStep;
        return (
          <div key={step.label}>
            {step.group && <div className="navgrp">{t(step.group)}</div>}
            <button
              type="button"
              onClick={() => onStepClick(i)}
              className={`step${isActive ? " on" : ""}${isDone ? " done" : ""}`}
            >
              <div className="c">
                {isDone ? <i className="ti ti-check" style={{ fontSize: 13 }} /> : i + 1}
              </div>
              <div style={{ minWidth: 0 }}>
                <div className="t1">
                  {t(step.label)}
                  {step.tag && <span className={`tag ${step.tag.tone}`}>{t(step.tag.label)}</span>}
                  {!!requiredBadge && requiredBadge > 0 && (
                    <span className="step-req" title={requiredBadge === 1 ? t("{count} required field left", { count: requiredBadge }) : t("{count} required fields left", { count: requiredBadge })}>{requiredBadge}</span>
                  )}
                </div>
                <div className="t2">{t(step.sub)}</div>
              </div>
            </button>
          </div>
        );
      })}

      {totalMissing > 0 && (
        <div className="hw-missing">
          <div className="hw-missing-title"><i className="ti ti-alert-circle" /> {totalMissing === 1 ? t("{count} field still required", { count: totalMissing }) : t("{count} fields still required", { count: totalMissing })}</div>
          {Object.entries(missingByStep).filter(([, fields]) => fields.length > 0).map(([stepIdx, fields]) => (
            <button key={stepIdx} type="button" className="hw-missing-row" onClick={() => onStepClick(Number(stepIdx))}>
              <span>{t(steps[Number(stepIdx)]?.label ?? "")}</span>
              <small>{fields.slice(0, 3).join(", ")}{fields.length > 3 ? ` ${t("+{count} more", { count: fields.length - 3 })}` : ""}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
