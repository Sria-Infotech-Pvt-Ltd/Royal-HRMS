"use client";

import { useT } from "@/hooks/useI18n";
import type { ApprovalChain } from "@/types/approvers";
import { personLine } from "./approverLabels";

/** True when the request must not be sent yet: the chain cannot finish, or it has gaps the employee has not acknowledged. */
export function chainBlocksSubmit(chain: ApprovalChain | null, acknowledged: boolean): boolean {
  if (!chain) return false;   // could not be loaded: the server still refuses a chain that cannot finish
  return !chain.can_submit || (chain.warnings.length > 0 && !acknowledged);
}

interface Props {
  chain: ApprovalChain | null;
  loading?: boolean;
  acknowledged: boolean;
  onAcknowledge: (next: boolean) => void;
}

/** Who will approve this leave request, stage by stage, shown before it is submitted. */
export default function ApprovalChainPreview({ chain, loading, acknowledged, onAcknowledge }: Props) {
  const t = useT();
  if (loading) return <p style={{ color: "var(--on-variant)", fontSize: 13 }}>{t("Checking who will approve this request…")}</p>;
  if (!chain) return null;
  return (
    <div className="rvcard" style={{ marginBottom: 16 }}>
      <h4><i className="ti ti-route" /> {t("WHO WILL APPROVE THIS REQUEST")}</h4>
      <ol style={{ margin: "0 0 4px", paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
        {chain.stages.map(stage => (
          <li key={stage.stage}>
            <b>{stage.label}:</b>{" "}
            {stage.status === "assigned" && stage.user ? personLine(stage.user) : null}
            {stage.status === "skipped" && <span style={{ color: "var(--on-variant)" }}>{t("not needed.")} {stage.note}</span>}
            {stage.status === "missing" && <span style={{ color: "var(--error)" }}>{t("Not assigned")}</span>}
          </li>
        ))}
      </ol>
      {chain.blocking.map(message => <div key={message} className="alert alert-error" style={{ marginTop: 10 }}>{message}</div>)}
      {chain.can_submit && chain.warnings.length > 0 && (
        <div className="alert alert-warn" style={{ marginTop: 10 }}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>{chain.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>
          <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, fontWeight: 600 }}>
            <input type="checkbox" checked={acknowledged} onChange={event => onAcknowledge(event.target.checked)} />
            {t("I understand and want to submit anyway")}
          </label>
        </div>
      )}
    </div>
  );
}
