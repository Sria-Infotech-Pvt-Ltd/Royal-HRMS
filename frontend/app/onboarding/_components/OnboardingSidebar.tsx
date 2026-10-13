"use client";

// Left rail for the self-service onboarding wizard — same visual language
// (.wiz-nav/.step/.navgrp, aira-theme.css) as the Hire wizard's
// HireWizardSidebar, so "complete your onboarding" and "hire an employee"
// read as one consistent product instead of two different wizard styles.
// Unlike HireWizardSidebar (free-jump, HR fills this out), a step here stays
// locked until the one before it is actually saved — same rule
// StepIndicator has always enforced for this wizard, just carried over
// rather than loosened.

export interface OnboardingStepDef {
  label: string;
  shortLabel: string;
  icon: string;
}

interface Props {
  steps: OnboardingStepDef[];
  currentStep: number;
  highestSaved: number;
  onStepClick: (index: number) => void;
}

export default function OnboardingSidebar({ steps, currentStep, highestSaved, onStepClick }: Props) {
  return (
    <div className="wiz-nav">
      {steps.map((step, i) => {
        const isDone      = i <= highestSaved;
        const isActive    = i === currentStep;
        const isReachable = i <= highestSaved + 1;
        return (
          <button
            key={step.label}
            type="button"
            onClick={() => { if (isReachable) onStepClick(i); }}
            disabled={!isReachable}
            className={`step${isActive ? " on" : ""}${isDone ? " done" : ""}`}
            style={{ opacity: isReachable ? 1 : 0.45, cursor: isReachable ? "pointer" : "default" }}
          >
            <div className="c">
              {isDone ? <i className="ti ti-check" style={{ fontSize: 13 }} /> : i + 1}
            </div>
            <div style={{ minWidth: 0 }}>
              <div className="t1">{step.shortLabel}</div>
              <div className="t2">{isDone ? "Done" : isActive ? "In progress" : `Step ${i + 1}`}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
