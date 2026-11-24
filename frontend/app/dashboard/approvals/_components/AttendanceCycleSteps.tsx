"use client";

// The sign-off chain for one payroll attendance cycle, drawn as three steps:
// each manager signs off their team, then L1 closes the manager stage, then HR gives the final L2 approval.
import type { ManagerApproval } from "@/types/payroll";
import { useT } from "@/hooks/useI18n";

interface Props {
  managers: ManagerApproval[];
  managersApproved: number;
  managersTotal: number;
  isL1Done: boolean;
  isL2Done: boolean;
  l2Name: string | null;
  isHrSelfApproved: boolean;
}

type StepState = "done" | "current" | "waiting";

function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function AttendanceCycleSteps({ managers, managersApproved, managersTotal, isL1Done, isL2Done, l2Name, isHrSelfApproved }: Props) {
  const t = useT();
  const managersDone = managersTotal > 0 && managersApproved === managersTotal;
  const steps: { title: string; detail: string; state: StepState; icon: string }[] = [
    {
      title: t("Managers sign off"),
      detail: managersTotal > 0 ? t("{approved} of {total} managers", { approved: managersApproved, total: managersTotal }) : t("No team leads set up"),
      state: managersTotal === 0 || managersDone || isL1Done ? "done" : "current",
      icon: "ti-users",
    },
    {
      title: t("L1 approval"),
      detail: isL1Done ? t("Approved") : t("Waiting"),
      state: isL1Done ? "done" : managersTotal === 0 || managersDone ? "current" : "waiting",
      icon: "ti-user-check",
    },
    {
      title: t("L2 · HR final sign-off"),
      detail: isL2Done ? (l2Name ? t("Approved by {name}", { name: l2Name }) : t("Approved")) : t("Waiting"),
      state: isL2Done ? "done" : isL1Done ? "current" : "waiting",
      icon: "ti-shield-check",
    },
  ];

  return (
    <div className="aa-steps-wrap">
      <ol className="aa-steps" aria-label={t("Approval progress")}>
        {steps.map(step => (
          <li key={step.title} className={`aa-step is-${step.state}`} aria-current={step.state === "current" ? "step" : undefined}>
            <span className="aa-step-dot"><i className={`ti ${step.state === "done" ? "ti-check" : step.icon}`} /></span>
            <div>
              <div className="aa-step-title">{step.title}</div>
              <div className="aa-step-detail">{step.detail}</div>
            </div>
          </li>
        ))}
      </ol>

      {isHrSelfApproved && <span className="aa-tag">{t("HR self-approved")}</span>}

      {managers.length > 0 && (
        <div className="aa-managers">
          {managers.map(row => (
            <span key={row.id} className={`aa-manager${row.approved_at ? " is-done" : ""}`}>
              <i className={`ti ${row.approved_at ? "ti-circle-check" : "ti-clock"}`} />
              <b>{row.manager_name}</b>
              {row.approved_at && <small>{dateTime(row.approved_at)}</small>}
              {row.self_approved_at && <em>{t("Self-approved")}</em>}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
