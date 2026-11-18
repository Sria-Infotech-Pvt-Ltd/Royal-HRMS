"use client";

import type { CSSProperties } from "react";
import { FALLBACK_LOOK, LOOK, type WorkflowCardData } from "./ApprovalWorkflowCard";

interface Props {
  row: WorkflowCardData;
  actionLabel: string;
  onAction: () => void;
}

/** One workflow as a slim queue line: icon, name and who sees it, count pills, and the way in. */
export default function ApprovalWorkflowRow({ row, actionLabel, onAction }: Props) {
  const look = LOOK[row.key] ?? FALLBACK_LOOK;
  const needsMe = (row.mine ?? 0) > 0;
  return (
    <div className={`ap-line${needsMe ? " needs-me" : ""}`} style={{ "--ap-accent": look.colour } as CSSProperties}>
      <span className="ap-icon"><i className={`ti ${look.icon}`} /></span>
      <div className="ap-line-main">
        <div className="ap-line-title">{row.label}</div>
        <div className="ap-line-scope" title={row.scope}>{row.scope}</div>
      </div>
      {row.pending === null && row.mine === null ? (
        <span className="ap-pill">See inside tab</span>
      ) : (
        <>
          <span className="ap-pill" title="Waiting"><i className="ti ti-hourglass" /> {row.pending ?? "—"} waiting</span>
          <span className={`ap-pill${needsMe ? " is-hot" : ""}`} title="For me to act on"><i className="ti ti-bolt" /> {row.mine ?? "—"} for me</span>
        </>
      )}
      <button type="button" className={`btn btn-sm ${needsMe ? "btn-filled" : "btn-outline"}`} onClick={onAction}>{actionLabel}</button>
    </div>
  );
}
