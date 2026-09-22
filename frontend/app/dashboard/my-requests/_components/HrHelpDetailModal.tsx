"use client";

import Modal from "@/components/Modal";
import type { HrHelpRequest } from "@/types/hrHelp";
import { STATUS_BADGE_CLASS, STATUS_LABEL, fmtSubmitted, hrHelpToDisplayStatus } from "../_data";

interface Props {
  request: HrHelpRequest;
  onClose: () => void;
}

export default function HrHelpDetailModal({ request: r, onClose }: Props) {
  const displayStatus = hrHelpToDisplayStatus(r.status, r.topic);

  return (
    <Modal
      title={<><i className="ti ti-headset" style={{ marginRight: 8 }} /> {r.topic_display}</>}
      onClose={onClose}
      maxWidth="min(480px, 95vw)"
      footer={<button className="btn btn-ghost" onClick={onClose}>Close</button>}
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Reference</p>
            <p className="text-sm font-medium text-[var(--on-bg)]">{r.request_ref || "—"}</p>
          </div>
          <span className={STATUS_BADGE_CLASS[displayStatus]}>{STATUS_LABEL[displayStatus]}</span>
        </div>

        <div className="border-t border-[var(--outline-v)] pt-4">
          <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Message</p>
          <p className="text-sm text-[var(--on-bg)] whitespace-pre-wrap">{r.message}</p>
        </div>

        {r.response && (
          <div className="border-t border-[var(--outline-v)] pt-4">
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">HR response</p>
            <p className="text-sm text-[var(--on-bg)] whitespace-pre-wrap">{r.response}</p>
          </div>
        )}

        <div className="border-t border-[var(--outline-v)] pt-4 flex items-center justify-between text-sm">
          <span className="text-[var(--on-variant)]">Priority</span>
          <span className="font-medium">{r.priority_display}</span>
        </div>

        {r.assigned_to_name && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-[var(--on-variant)]">Assigned to</span>
            <span className="font-medium">{r.assigned_to_name}</span>
          </div>
        )}

        <div className="text-xs text-[var(--on-variant)] border-t border-[var(--outline-v)] pt-3">
          Submitted {fmtSubmitted(r.created_at)}
          {r.resolved_at && <> · Resolved {fmtSubmitted(r.resolved_at)}</>}
        </div>
      </div>
    </Modal>
  );
}
