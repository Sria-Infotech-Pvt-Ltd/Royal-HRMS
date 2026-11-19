"use client";

import type { CSSProperties } from "react";

export interface WorkflowCardData {
  key: string;
  label: string;
  scope: string;
  pending: number | null;
  mine: number | null;
}

export const LOOK: Record<string, { icon: string; colour: string }> = {
  leave:                  { icon: "ti-beach",           colour: "var(--brand)" },
  wfh:                    { icon: "ti-home-2",          colour: "#0ea5e9" },
  expense:                { icon: "ti-wallet",          colour: "#16a34a" },
  attendance_correction:  { icon: "ti-clock-edit",      colour: "#d97706" },
  separation:             { icon: "ti-door-exit",       colour: "#dc2626" },
  face:                   { icon: "ti-face-id",         colour: "#0d9488" },
  attendance:             { icon: "ti-calendar-check",  colour: "#2563eb" },
  timesheets:             { icon: "ti-clock-hour-4",    colour: "#9333ea" },
  personnel:              { icon: "ti-arrows-exchange", colour: "#ea580c" },
  profile_corrections:    { icon: "ti-user-edit",       colour: "#db2777" },
};
export const FALLBACK_LOOK = { icon: "ti-inbox", colour: "#6b7280" };

interface Props {
  row: WorkflowCardData;
  actionLabel: string;
  onAction: () => void;
}

/** One workflow: how many requests are waiting, how many are this person's to decide, and the way in. */
export default function ApprovalWorkflowCard({ row, actionLabel, onAction }: Props) {
  const look = LOOK[row.key] ?? FALLBACK_LOOK;
  const isCounted = row.pending !== null || row.mine !== null;
  const needsMe = (row.mine ?? 0) > 0;
  return (
    <article className={`ap-card${needsMe ? " needs-me" : ""}`} style={{ "--ap-accent": look.colour } as CSSProperties}>
      <div className="ap-card-top">
        <span className="ap-icon"><i className={`ti ${look.icon}`} /></span>
        <h3>{row.label}</h3>
        {needsMe && <span className="ap-flag">Needs you</span>}
      </div>

      {isCounted ? (
        <div className="ap-counts">
          <div><b>{row.pending ?? "—"}</b><span>Waiting</span></div>
          <div className={needsMe ? "is-hot" : ""}><b>{row.mine ?? "—"}</b><span>For me to act on</span></div>
        </div>
      ) : (
        <div className="ap-uncounted"><i className="ti ti-info-circle" /> Counts are shown inside the tab.</div>
      )}

      <p className="ap-scope" title={row.scope}>{row.scope}</p>
      <button type="button" className={`btn btn-sm ${needsMe ? "btn-filled" : "btn-outline"}`} onClick={onAction}>
        {actionLabel} <i className="ti ti-arrow-right" />
      </button>
    </article>
  );
}
