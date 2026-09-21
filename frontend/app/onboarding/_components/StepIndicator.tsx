"use client";

// The numbered-circle step progress indicator used by the onboarding wizard.
// Pure/prop-driven — shared by the self-service wizard (app/onboarding/page.tsx)
// and the HR-completes-onboarding wizard
// (app/dashboard/employees/[id]/onboarding/page.tsx), so both present the
// exact same step-by-step wizard experience instead of two different UIs for
// the same underlying flow.

export interface StepDef {
  label: string;
  shortLabel: string;
  icon: string;
}

interface Props {
  steps: StepDef[];
  currentStep: number;
  highestSaved: number;
  onStepClick: (index: number) => void;
}

// A step stays locked until the one before it is actually saved — both the
// self-service wizard and HR's "Complete Onboarding" (on an employee's
// behalf) enforce the same sequential order; HR used to be able to jump
// freely between steps, but that let HR advance to a later step while an
// earlier one's required fields were still blank, which isn't wanted.
export default function StepIndicator({ steps, currentStep, highestSaved, onStepClick }: Props) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "center", marginBottom: "2.5rem", overflowX: "auto", padding: "0 .5rem" }}>
      {steps.map((step, i) => {
        const isDone      = i <= highestSaved;
        const isActive    = i === currentStep;
        const isReachable = i <= highestSaved + 1;
        return (
          <div key={step.label} style={{ display: "flex", alignItems: "flex-start", flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => { if (isReachable) onStepClick(i); }}
              disabled={!isReachable}
              style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, background: "none", border: "none", cursor: isReachable ? "pointer" : "default", padding: "0 4px", minWidth: 88, opacity: isReachable ? 1 : 0.45 }}
            >
              <div style={{
                width: 58, height: 58, borderRadius: "50%",
                display: "flex", alignItems: "center", justifyContent: "center",
                background: isDone ? "var(--success)" : isActive ? "var(--primary)" : "#fff",
                border: isDone ? "2.5px solid var(--success)" : isActive ? "2.5px solid var(--primary)" : "2px solid var(--outline-v)",
                boxShadow: isActive ? "0 0 0 5px rgba(124,58,237,0.12), 0 4px 12px rgba(124,58,237,0.18)" : isDone ? "0 2px 8px rgba(23,144,90,0.18)" : "none",
                transition: "all 0.25s ease",
              }}>
                {isDone
                  ? <i className="ti ti-check" style={{ fontSize: 24, color: "#fff" }} />
                  : <i className={`ti ${step.icon}`} style={{ fontSize: 22, color: isActive ? "#fff" : "var(--outline)" }} />
                }
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: isDone ? "var(--success)" : isActive ? "var(--primary)" : "var(--outline)", marginBottom: 3 }}>
                  {isDone ? "Done" : `Step ${i + 1}`}
                </div>
                <div style={{ fontSize: 12, fontWeight: isActive ? 700 : 500, color: isActive ? "var(--on-bg)" : isDone ? "var(--success)" : "var(--on-variant)", maxWidth: 80, lineHeight: 1.3 }}>
                  {step.shortLabel}
                </div>
              </div>
            </button>

            {i < steps.length - 1 && (
              <div style={{ display: "flex", alignItems: "center", paddingTop: 29, margin: "0 -4px" }}>
                <div style={{ width: 28, height: 2, background: i <= highestSaved ? "var(--success)" : "var(--outline-v)", borderRadius: 2, transition: "background 0.3s" }} />
                <i className="ti ti-chevron-right" style={{ fontSize: 14, color: i <= highestSaved ? "var(--success)" : "var(--outline-v)", margin: "0 -2px", transition: "color 0.3s" }} />
                <div style={{ width: 28, height: 2, background: i <= highestSaved ? "var(--success)" : "var(--outline-v)", borderRadius: 2, transition: "background 0.3s" }} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
