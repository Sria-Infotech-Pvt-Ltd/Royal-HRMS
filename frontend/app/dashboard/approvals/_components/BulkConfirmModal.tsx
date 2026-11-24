"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import { useT } from "@/hooks/useI18n";

interface Props {
  action:  "approve" | "reject";
  count:   number;
  saving:  boolean;
  onConfirm: (remarks: string) => void;
  onClose:   () => void;
}

export default function BulkConfirmModal({ action, count, saving, onConfirm, onClose }: Props) {
  const t = useT();
  const [remarks, setRemarks] = useState("");
  const isApprove = action === "approve";

  return (
    <Modal
      title={isApprove
        ? (count === 1 ? t("Approve {count} request", { count }) : t("Approve {count} requests", { count }))
        : (count === 1 ? t("Reject {count} request", { count }) : t("Reject {count} requests", { count }))}
      onClose={onClose}
      maxWidth={480}
      footer={
        <>
          <button className="btn btn-ghost" suppressHydrationWarning onClick={onClose} disabled={saving}>
            {t("Cancel")}
          </button>
          <button
            className={`btn ${isApprove ? "btn-success" : "btn-danger"}`}
            suppressHydrationWarning
            disabled={saving || (!isApprove && !remarks.trim())}
            onClick={() => onConfirm(remarks)}
          >
            {saving ? (
              <><i className="ti ti-loader-2 spin" /> {t("Saving…")}</>
            ) : isApprove ? (
              <><i className="ti ti-check" /> {t("Approve {count}", { count })}</>
            ) : (
              <><i className="ti ti-x" /> {t("Reject {count}", { count })}</>
            )}
          </button>
        </>
      }
    >
      <div className={`alert ${isApprove ? "alert-info" : "alert-warn"} mb-16`}>
        <i className={`ti ${isApprove ? "ti-info-circle" : "ti-alert-triangle"}`} />
        <div>
          {isApprove
            ? (count === 1 ? t("You're about to approve {count} selected request. Employees will be notified.", { count }) : t("You're about to approve {count} selected requests. Employees will be notified.", { count }))
            : (count === 1 ? t("You're about to reject {count} selected request. Employees will be notified.", { count }) : t("You're about to reject {count} selected requests. Employees will be notified.", { count }))}
        </div>
      </div>

      <div className="field-group">
        <label className="field-label">
          {t("Remarks")} {!isApprove && <span style={{ color: "var(--error)" }}>*</span>}
        </label>
        <textarea
          className="field-input"
          rows={3}
          placeholder={isApprove ? t("Optional notes for the record…") : t("Reason for rejection (required)")}
          value={remarks}
          onChange={e => setRemarks(e.target.value)}
          style={{ resize: "vertical" }}
        />
      </div>
    </Modal>
  );
}
