"use client";

// Right column of "My appraisal" — the 4-step vertical review-stage
// tracker. Reuses the app's existing timeline classes (tl-item/tl-dot/
// tl-body/tl-title/tl-desc — see ManagerDashboard.tsx's activity feed and
// globals.css) rather than inventing new stepper CSS.

import { formatDate } from "@/lib/formatDate";

export interface AppraisalStageInput {
  selfSubmittedAt: string | null;
  managerSubmittedAt: string | null;
  hrCalibratedAt: string | null;
  publishedAt: string | null;
  acknowledgedAt: string | null;
  selfReviewDue: string | null;
  managerReviewDue: string | null;
}

type StepState = "done" | "current" | "pending";

interface Step {
  title: string;
  desc: string;
  state: StepState;
}

function dotClass(state: StepState): string {
  if (state === "done") return "tl-success";
  if (state === "current") return "tl-info";
  return "tl-neutral";
}

function dotIcon(state: StepState): string {
  if (state === "done") return "ti-check";
  if (state === "current") return "ti-clock";
  return "ti-point";
}

function buildSteps(input: AppraisalStageInput): Step[] {
  const {
    selfSubmittedAt, managerSubmittedAt, hrCalibratedAt, publishedAt, acknowledgedAt,
  } = input;

  const selfDone    = !!selfSubmittedAt;
  const managerDone = !!managerSubmittedAt;
  const hrDone      = !!hrCalibratedAt;
  const publishDone = !!acknowledgedAt || !!publishedAt;

  return [
    {
      title: "Self-review",
      desc: "Employee reflects on outcomes and evidence",
      state: selfDone ? "done" : "current",
    },
    {
      title: "Manager review",
      desc: "Reporting manager assesses performance",
      state: managerDone ? "done" : selfDone ? "current" : "pending",
    },
    {
      title: "HR calibration",
      desc: "HR confirms the final rating and consistency",
      state: hrDone ? "done" : managerDone ? "current" : "pending",
    },
    {
      title: "Publish & acknowledge",
      desc: "Employee reads and acknowledges the outcome",
      state: publishDone ? "done" : hrDone ? "current" : "pending",
    },
  ];
}

export default function AppraisalStageTracker({ input }: { input: AppraisalStageInput }) {
  const steps = buildSteps(input);

  return (
    <div className="card mb-16">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-timeline" /> Review stages</div>
      </div>
      <div style={{ padding: "4px 20px 16px" }}>
        <p style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 8 }}>
          Due: self-review {input.selfReviewDue ? formatDate(input.selfReviewDue) : "—"} · manager review {input.managerReviewDue ? formatDate(input.managerReviewDue) : "—"}.
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
