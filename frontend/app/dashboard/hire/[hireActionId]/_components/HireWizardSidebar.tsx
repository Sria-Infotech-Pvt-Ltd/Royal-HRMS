"use client";

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
export default function HireWizardSidebar({ steps, currentStep, highestSaved, onStepClick, missingByStep }: Props) {
  const totalMissing = Object.values(missingByStep).reduce((n, arr) => n + arr.length, 0);

  return (
    <div className="wiz-nav">
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
        const isActive    = i === currentStep;
        return (
          <div key={step.label}>
            {step.group && <div className="navgrp">{step.group}</div>}
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
                  {step.label}
                  {step.tag && <span className={`tag ${step.tag.tone}`}>{step.tag.label}</span>}
                  {!!step.required && step.required > 0 && (
                    <span style={{ fontSize: 9.5, fontWeight: 700, color: "var(--onbrand)", background: "var(--crit)", borderRadius: 99, padding: "1px 5px" }}>
                      {step.required}
                    </span>
                  )}
                </div>
                <div className="t2">{step.sub}</div>
              </div>
            </button>
          </div>
        );
      })}

      {totalMissing > 0 && (
        <div style={{ marginTop: 16, padding: "10px 12px", borderRadius: "var(--r-field)", background: "var(--brand-tint)" }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--brand-ink)", marginBottom: 6 }}>
            {totalMissing} field{totalMissing === 1 ? "" : "s"} still required
          </div>
          {Object.entries(missingByStep).filter(([, f]) => f.length > 0).slice(0, 2).map(([stepIdx, fields]) => (
            <div key={stepIdx} style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--muted)" }}>
                {steps[Number(stepIdx)]?.label}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink)" }}>
                {fields.slice(0, 3).join(", ")}{fields.length > 3 ? ` +${fields.length - 3} more` : ""}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
