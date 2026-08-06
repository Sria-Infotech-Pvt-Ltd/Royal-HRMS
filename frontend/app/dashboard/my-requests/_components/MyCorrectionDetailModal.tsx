"use client";

import { MyCorrectionRequest, STATUS_BADGE_CLASS, STATUS_LABEL, fmtSubmitted, fmtTime12h, toDisplayStatus } from "../_data";

interface Props {
  request: MyCorrectionRequest;
  onClose: () => void;
}

const PUNCH_LABEL: Record<MyCorrectionRequest["punch_type"], string> = {
  IN:   "Check-in Correction",
  OUT:  "Check-out Correction",
  BOTH: "Check-in & Check-out Correction",
};

function StageRow({ label, approverName, status, remarks }: {
  label: string; approverName: string | null; status: "approved" | "rejected" | null; remarks: string;
}) {
  const cls = status === "approved" ? "badge badge-success" : status === "rejected" ? "badge badge-error" : "badge badge-warn";
  const txt = status === "approved" ? "Approved" : status === "rejected" ? "Rejected" : "Pending";
  return (
    <div className="flex items-start justify-between gap-3 py-2 border-b border-[var(--outline-v)] last:border-b-0">
      <div>
        <div className="text-sm font-medium text-[var(--on-bg)]">{label}</div>
        <div className="text-xs text-[var(--on-variant)] mt-0.5">{approverName || "Not yet assigned"}</div>
        {remarks && <div className="text-xs text-[var(--on-variant)] bg-[var(--bg-low)] rounded-md px-2 py-1 mt-1.5">&ldquo;{remarks}&rdquo;</div>}
      </div>
      <span className={cls}>{txt}</span>
    </div>
  );
}

export default function MyCorrectionDetailModal({ request: r, onClose }: Props) {
  const showIn  = r.punch_type !== "OUT";
  const showOut = r.punch_type !== "IN";

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ width: "min(480px, 95vw)", maxHeight: "90vh", overflowY: "auto" }}>
        <div className="modal-header">
          <div className="modal-title">
            <i className="ti ti-clock-edit" style={{ marginRight: 8 }} />
            {PUNCH_LABEL[r.punch_type] ?? "Attendance Correction"}
          </div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Date</p>
              <p className="text-sm font-medium text-[var(--on-bg)]">{fmtSubmitted(r.date)}</p>
            </div>
            <span className={STATUS_BADGE_CLASS[toDisplayStatus(r.status)]}>{STATUS_LABEL[toDisplayStatus(r.status)]}</span>
          </div>

          <div className="border-t border-[var(--outline-v)] pt-4 flex flex-col gap-2">
            {showIn && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-[var(--on-variant)]">Check-in</span>
                <span className="font-medium tabular-nums">{fmtTime12h(r.original_in)} → {fmtTime12h(r.requested_in)}</span>
              </div>
            )}
            {showOut && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-[var(--on-variant)]">Check-out</span>
                <span className="font-medium tabular-nums">{fmtTime12h(r.original_out)} → {fmtTime12h(r.requested_out)}</span>
              </div>
            )}
          </div>

          <div className="border-t border-[var(--outline-v)] pt-4">
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Reason</p>
            <p className="text-sm text-[var(--on-bg)]">{r.reason || "—"}</p>
            {r.notes && <p className="text-xs text-[var(--on-variant)] mt-1">{r.notes}</p>}
          </div>

          <div className="border-t border-[var(--outline-v)] pt-3">
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Approval Trail</p>
            <StageRow label="Manager Approval" approverName={r.l1_approver_name} status={r.l1_status} remarks={r.l1_remarks} />
            {r.l2_approver_name && (
              <StageRow label="HR Approval" approverName={r.l2_approver_name} status={r.l2_status} remarks={r.l2_remarks} />
            )}
          </div>

          <div className="text-xs text-[var(--on-variant)] border-t border-[var(--outline-v)] pt-3">
            Submitted {fmtSubmitted(r.created_at)}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
