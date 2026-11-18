"use client";

// A request's journey drawn as a line of steps joined by moving dashes: Submitted, Level 1, Level 2 (only when there is one), Approved.
// A named person shows their initials; "Reporting manager" and "HR partner" show an icon. Used in the list and in the editor, where it
// changes live as the approvers are chosen.

import { BRAND, initialsOf, tint, type FlowStep } from "./approvalFlowView";

export default function ApprovalFlow({ steps, compact = false }: { steps: FlowStep[]; compact?: boolean }) {
  const size = compact ? 30 : 36;
  return (
    <ol aria-label="Approval flow" style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", alignItems: "center", flexWrap: "wrap", gap: compact ? 6 : 8 }}>
      {steps.map((step, index) => {
        const isEnd = step.key === "submit" || step.key === "done";
        return (
          <li key={step.key} style={{ display: "flex", alignItems: "center", gap: compact ? 6 : 8 }}>
            <div
              data-step={step.key}
              style={{ display: "flex", alignItems: "center", gap: 9, padding: compact ? "6px 12px 6px 6px" : "8px 16px 8px 8px", borderRadius: 12, minWidth: 0, background: step.isMissing ? "transparent" : "var(--surface)", border: `1.5px ${step.isMissing ? "dashed" : "solid"} ${step.isMissing ? "var(--outline)" : "var(--outline-v)"}` }}
            >
              <span aria-hidden="true" style={{ width: size, height: size, borderRadius: size / 2.6, flexShrink: 0, display: "grid", placeItems: "center", fontSize: step.kind === "person" ? 12 : compact ? 16 : 18, fontWeight: 800, background: isEnd ? "var(--bg-low)" : tint(BRAND, 0.12), color: isEnd ? "var(--on-variant)" : BRAND, border: 0 }}>
                {step.kind === "person" ? initialsOf(step.detail) : <i className={`ti ${step.icon}`} />}
              </span>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--on-variant)" }}>{step.title}</div>
                <div style={{ fontSize: compact ? 12.5 : 13.5, fontWeight: 700, color: step.isMissing ? "var(--on-variant)" : "var(--on-bg)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 190 }}>{step.detail}</div>
              </div>
            </div>
            {index < steps.length - 1 && <span className="ar-connector" aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}
