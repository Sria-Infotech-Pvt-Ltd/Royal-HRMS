"use client";

import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";
import { useMyApprovals } from "@/hooks/useMyApprovals";
import type { ApprovalChain, ApprovalStage } from "@/types/approvers";
import { personLine } from "./approverLabels";

function stageValue(stage: ApprovalStage | undefined): { text: string; muted: boolean } {
  const notAssigned = tr("Not assigned");
  if (!stage || stage.status === "missing") return { text: notAssigned, muted: true };
  if (stage.status === "skipped") return { text: tr("Not needed: managers' leave goes straight to HR"), muted: true };
  return { text: stage.user ? personLine(stage.user) : notAssigned, muted: !stage.user };
}

function Line({ label, text, muted }: { label: string; text: string; muted?: boolean }) {
  return (
    <div className="kv">
      <span>{label}</span>
      <b style={muted ? { fontWeight: 500, color: "var(--on-variant)" } : undefined}>{text}</b>
    </div>
  );
}

/** The card's content for one chain; read-only by design (an employee cannot change who approves their requests). */
export function ReportingApprovalsView({ chain }: { chain: ApprovalChain }) {
  const t = useT();
  const manager = chain.reporting_manager;
  const l1 = stageValue(chain.stages.find(stage => stage.stage === "l1"));
  const l2 = stageValue(chain.stages.find(stage => stage.stage === "l2"));
  return (
    <>
      <div className="kvlist">
        <Line label={t("Reporting manager")} text={manager ? personLine(manager) : t("Not assigned")} muted={!manager} />
        <Line label={t("L1 approver")} text={l1.text} muted={l1.muted} />
        <Line label={t("L2 HR approver")} text={l2.text} muted={l2.muted} />
      </div>
      {chain.warnings.length > 0 && (
        <ul style={{ margin: "12px 0 0", paddingLeft: 18, fontSize: 12.5, color: "var(--on-variant)" }}>
          {chain.warnings.map(warning => <li key={warning}>{warning}</li>)}
        </ul>
      )}
      <p style={{ margin: "12px 0 0", fontSize: 12, color: "var(--on-variant)" }}>
        {t("These people approve your leave requests. Ask HR if something here is wrong or missing.")}
      </p>
    </>
  );
}

/** "Your Reporting & Approvals": the employee's own reporting manager, L1 and L2 approvers, with a clear "Not assigned" state. */
export default function ReportingApprovalsCard() {
  const t = useT();
  const { chain, loading, error } = useMyApprovals();
  return (
    <div className="rvcard" style={{ marginBottom: 20 }}>
      <h4><i className="ti ti-users" /> {t("YOUR REPORTING & APPROVALS")}</h4>
      {loading && <p style={{ margin: 0, color: "var(--on-variant)" }}>{t("Loading…")}</p>}
      {!loading && (error || !chain) && <p style={{ margin: 0, color: "var(--on-variant)" }}>{t("Could not load your approvers right now.")}</p>}
      {!loading && chain && <ReportingApprovalsView chain={chain} />}
    </div>
  );
}
