"use client";

import { useState } from "react";
import Modal from "@/components/Modal";

interface Props {
  action:  "approve" | "reject";
  count:   number;
  saving:  boolean;
  onConfirm: (remarks: string) => void;
  onClose:   () => void;
}

export default function BulkConfirmModal({ action, count, saving, onConfirm, onClose }: Props) {
  const [remarks, setRemarks] = useState("");
  const isApprove = action === "approve";

  return (
    <Modal
      title={`${isApprove ? "Approve" : "Reject"} ${count} request${count === 1 ? "" : "s"}`}
      onClose={onClose}
      maxWidth={480}
      footer={
        <>
          <button className="btn btn-ghost" suppressHydrationWarning onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            className={`btn ${isApprove ? "btn-success" : "btn-danger"}`}
            suppressHydrationWarning
            disabled={saving || (!isApprove && !remarks.trim())}
            onClick={() => onConfirm(remarks)}
          >
            {saving ? (
              <><i className="ti ti-loader-2 spin" /> Saving…</>
            ) : isApprove ? (
              <><i className="ti ti-check" /> Approve {count}</>
            ) : (
              <><i className="ti ti-x" /> Reject {count}</>
            )}
          </button>
        </>
      }
    >
      <div className={`alert ${isApprove ? "alert-info" : "alert-warn"} mb-16`}>
        <i className={`ti ${isApprove ? "ti-info-circle" : "ti-alert-triangle"}`} />
        <div>
          {isApprove
            ? `You're about to approve ${count} selected request${count === 1 ? "" : "s"}. Employees will be notified.`
            : `You're about to reject ${count} selected request${count === 1 ? "" : "s"}. Employees will be notified.`}
        </div>
      </div>

      <div className="field-group">
        <label className="field-label">
          Remarks {!isApprove && <span style={{ color: "var(--error)" }}>*</span>}
        </label>
        <textarea
          className="field-input"
          rows={3}
          placeholder={isApprove ? "Optional notes for the record…" : "Reason for rejection (required)"}
          value={remarks}
          onChange={e => setRemarks(e.target.value)}
          style={{ resize: "vertical" }}
        />
      </div>
    </Modal>
  );
}
