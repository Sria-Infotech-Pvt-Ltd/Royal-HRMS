"use client";

import { useRef, useState } from "react";

interface Props {
  action:       "approve" | "reject";
  employeeName: string;
  onClose:      () => void;
  onConfirm:    (comment: string) => void;
  saving:       boolean;
}

export default function DecisionModal({ action, employeeName, onClose, onConfirm, saving }: Props) {
  const isApprove = action === "approve";
  const [comment, setComment] = useState("");
  // A click's target is resolved at mouseup, not mousedown — selecting text
  // inside the comment field and releasing past the modal's edge would
  // otherwise land on the overlay and close it mid-input. Only close when
  // the gesture both started AND ended on the backdrop itself.
  const mouseDownOnOverlay = useRef(false);

  return (
    <div
      className="modal-overlay open"
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) onClose(); }}
    >
      <div className="modal" style={{ width: "min(480px, 95vw)" }}>
        <div className="modal-header">
          <div className="modal-title">
            {isApprove ? "Approve" : "Reject"} — {employeeName}
          </div>
          <button className="modal-close" onClick={onClose} suppressHydrationWarning>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          {!isApprove && (
            <div className="alert alert-warn mb-16">
              <i className="ti ti-alert-triangle" />
              <div>This request will be rejected and the workflow will stop here.</div>
            </div>
          )}
          <div className="field-group">
            <label className="field-label">
              Comment {!isApprove && <span style={{ color: "var(--error)" }}>*</span>}
            </label>
            <textarea
              className="field-input" rows={3} style={{ resize: "vertical" }}
              placeholder={isApprove ? "Optional notes for the record…" : "Reason for rejection (required)"}
              value={comment} onChange={e => setComment(e.target.value)}
            />
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving} suppressHydrationWarning>
            Cancel
          </button>
          <button
            className={`btn ${isApprove ? "btn-success" : "btn-danger"}`}
            disabled={saving || (!isApprove && !comment.trim())}
            onClick={() => onConfirm(comment.trim())}
            suppressHydrationWarning
          >
            {saving
              ? <><i className="ti ti-loader-2 spin" /> Saving…</>
              : isApprove ? <><i className="ti ti-check" /> Approve</> : <><i className="ti ti-x" /> Reject</>
            }
          </button>
        </div>
      </div>
    </div>
  );
}
