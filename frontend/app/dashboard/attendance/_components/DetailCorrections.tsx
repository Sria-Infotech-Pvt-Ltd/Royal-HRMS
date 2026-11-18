"use client";

// The day's correction requests as cards, with Approve / Reject on a pending one for someone who may review it.

import type { CorrectionReviewAction, CorrectionRow } from "@/types/attendance";
import { PALETTE, tint } from "./attendancePalette";
import { CORRECTION_STATUS, PUNCH_TYPE_LABEL } from "./detailView";

interface Props {
  corrections: CorrectionRow[];
  canReview: boolean;
  reviewingId: string | null;
  onReview: (id: string, action: CorrectionReviewAction) => void;
}

const when = (value: string | null) => value ?? "—";

export default function DetailCorrections({ corrections, canReview, reviewingId, onReview }: Props) {
  if (corrections.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "26px 12px", color: "var(--on-variant)" }}>
        <i className="ti ti-file-check" aria-hidden="true" style={{ fontSize: 30, color: "var(--outline)" }} />
        <div style={{ fontSize: 13, marginTop: 6 }}>No correction requests for this day.</div>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {corrections.map(correction => {
        const status = CORRECTION_STATUS[correction.status];
        const busy = reviewingId === correction.id;
        return (
          <article key={correction.id} aria-label={`${PUNCH_TYPE_LABEL[correction.punch_type]} correction, ${status.label}`} style={{ padding: "12px 14px", borderRadius: 12, border: "1px solid var(--outline-v)", borderLeft: `4px solid ${status.colour}` }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontWeight: 700, fontSize: 13.5 }}>{PUNCH_TYPE_LABEL[correction.punch_type]}</span>
              <span style={{ fontSize: 11.5, fontWeight: 700, padding: "2px 10px", borderRadius: 999, background: tint(status.colour, 0.14), color: status.colour }}>{status.label}</span>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
              <span style={{ fontSize: 12, padding: "3px 9px", borderRadius: 8, background: tint(PALETTE.present, 0.1) }}>In <strong style={{ fontFamily: "Menlo, Consolas, monospace" }}>{when(correction.requested_in)}</strong></span>
              <span style={{ fontSize: 12, padding: "3px 9px", borderRadius: 8, background: tint(PALETTE.half_day, 0.1) }}>Out <strong style={{ fontFamily: "Menlo, Consolas, monospace" }}>{when(correction.requested_out)}</strong></span>
            </div>
            <div style={{ fontSize: 12.5, color: "var(--on-variant)" }}>{correction.reason}</div>
            {correction.status === "pending" && canReview ? (
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button className="btn btn-filled btn-sm" disabled={busy} onClick={() => onReview(correction.id, "approve")} style={{ background: PALETTE.present }}><i className="ti ti-check" /> Approve</button>
                <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onReview(correction.id, "reject")} style={{ color: PALETTE.absent, borderColor: PALETTE.absent }}><i className="ti ti-x" /> Reject</button>
              </div>
            ) : (
              (correction.reviewed_by || correction.reviewed_at) && (
                <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 8 }}>Reviewed by {correction.reviewed_by ?? "—"}{correction.reviewed_at ? ` on ${correction.reviewed_at}` : ""}</div>
              )
            )}
          </article>
        );
      })}
    </div>
  );
}
