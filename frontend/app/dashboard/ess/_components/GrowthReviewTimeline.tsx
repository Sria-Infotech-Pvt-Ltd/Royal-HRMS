"use client";

// "Review timeline" card on Growth — a 3-stage dot timeline (goals agreed /
// self review / manager review), wired to the real review's
// self_submitted_at / manager_submitted_at and the cycle's own due dates
// rather than hardcoding which stage is current. Reuses the same
// .timeline/.tl-item/.tl-dot classes as AppraisalStageTracker.tsx instead
// of inventing new stepper CSS.

import { formatDate } from "@/lib/formatDate";

export interface GrowthTimelineInput {
  cycleName: string;
  cycleOpenedAt: string | null;
  selfReviewDue: string | null;
  managerReviewDue: string | null;
  selfSubmittedAt: string | null;
  managerSubmittedAt: string | null;
}

type StepState = "done" | "current" | "upcoming";

function dotClass(state: StepState): string {
  if (state === "done") return "tl-success";
  if (state === "current") return "tl-warn";
  return "tl-neutral";
}

function dotIcon(state: StepState): string {
  if (state === "done") return "ti-check";
  if (state === "current") return "ti-clock";
  return "ti-point";
}

function buildSteps(input: GrowthTimelineInput): { title: string; desc: string; state: StepState }[] {
  const selfDone = !!input.selfSubmittedAt;
  const managerDone = !!input.managerSubmittedAt;

  return [
    {
      title: "Goals agreed",
      desc: `${input.cycleName} cycle opened ${input.cycleOpenedAt ? formatDate(input.cycleOpenedAt) : "—"}`,
      state: "done",
    },
    {
      title: "Self review",
      desc: `Due ${input.selfReviewDue ? formatDate(input.selfReviewDue) : "—"}`,
      state: selfDone ? "done" : "current",
    },
    {
      title: "Manager review",
      desc: `Due ${input.managerReviewDue ? formatDate(input.managerReviewDue) : "—"}`,
      state: managerDone ? "done" : selfDone ? "current" : "upcoming",
    },
  ];
}

export default function GrowthReviewTimeline({ input }: { input: GrowthTimelineInput }) {
  const steps = buildSteps(input);

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-timeline" /> Review timeline</div>
      </div>
      <div style={{ padding: "4px 20px 20px" }}>
        <p style={{ margin: "0 0 8px", fontSize: 12.5, color: "var(--on-variant)" }}>
          Self review and manager review remain visible to the employee.
        </p>
        <div className="timeline">
          {steps.map(step => (
            <div key={step.title} className="tl-item">
              <div className={`tl-dot ${dotClass(step.state)}`}><i className={`ti ${dotIcon(step.state)}`} /></div>
              <div className="tl-body">
                <div className="tl-title">{step.title}</div>
                <div className="tl-desc">{step.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
