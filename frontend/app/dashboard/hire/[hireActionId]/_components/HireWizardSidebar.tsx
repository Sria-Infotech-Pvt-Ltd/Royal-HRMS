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
// check once passed, purple while active, gray + locked otherwise), a
// "RECORDS & COMPLIANCE" group header before step 5, and a running
// "N fields still required" box listing the first couple of incomplete
// steps' missing fields. Locking logic (isReachable/isDone) mirrors
// app/onboarding/_components/StepIndicator.tsx's own — a step stays locked
// until the one before it is actually saved.
export default function HireWizardSidebar({ steps, currentStep, highestSaved, onStepClick, missingByStep }: Props) {
  const totalMissing = Object.values(missingByStep).reduce((n, arr) => n + arr.length, 0);

  return (
    <div className="wiz-nav">
      {steps.map((step, i) => {
        const isDone      = i <= highestSaved;
        const isActive    = i === currentStep;
        const isReachable = i <= highestSaved + 1;
        return (
          <div key={step.label}>
            {step.group && <div className="navgrp">{step.group}</div>}
            <button
              type="button"
              onClick={() => { if (isReachable) onStepClick(i); }}
              disabled={!isReachable}
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
