import type { ApprovalStage, SeparationRequest } from "@/types/separation";
import { fmtDateTime, statusBadgeClass } from "../../_workflow";

function StageRow({ stage, onDecide }: { stage: ApprovalStage; onDecide: (action: "approve" | "reject") => void }) {
  const dotClass = stage.status.toLowerCase().includes("reject") ? "tl-error"
    : stage.status.toLowerCase().includes("approve") ? "tl-success" : "tl-neutral";
  const icon = stage.status.toLowerCase().includes("reject") ? "ti-x"
    : stage.status.toLowerCase().includes("approve") ? "ti-check" : "ti-clock";

  return (
    <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
      <div className={`tl-dot ${dotClass}`} style={{ flexShrink: 0 }}>
        <i className={`ti ${icon}`} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{stage.stage_display}</span>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={`badge ${statusBadgeClass(stage.status)}`}>{stage.status_display}</span>
            {stage.can_action && (
              <div style={{ display: "flex", gap: 6 }}>
                <button className="btn btn-danger btn-sm" onClick={() => onDecide("reject")} suppressHydrationWarning>
                  <i className="ti ti-x" /> Reject
                </button>
                <button className="btn btn-success btn-sm" onClick={() => onDecide("approve")} suppressHydrationWarning>
                  <i className="ti ti-check" /> Approve
                </button>
              </div>
            )}
          </div>
        </div>
        <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
          {stage.approver_name || "Not yet assigned"}{stage.actioned_at ? ` · ${fmtDateTime(stage.actioned_at)}` : ""}
        </div>
        {stage.remarks && (
          <div style={{ fontSize: 12, color: "var(--on-variant)", background: "var(--bg-low)", borderRadius: 8, padding: "6px 10px", marginTop: 6 }}>
            “{stage.remarks}”
          </div>
        )}
      </div>
    </div>
  );
}

interface Props {
  r:        SeparationRequest;
  onDecide: (stageId: string, action: "approve" | "reject") => void;
}

export default function ApprovalSection({ r, onDecide }: Props) {
  const stages = [...r.approval_stages].sort((a, b) => a.sequence - b.sequence);

  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-checks" /> Approval</span>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {stages.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}>No approval stages configured.</p>
        ) : (
          stages.map(stage => (
            <StageRow key={stage.id} stage={stage} onDecide={action => onDecide(stage.id, action)} />
          ))
        )}
      </div>
    </div>
  );
}
