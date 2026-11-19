"use client";

// One work-from-home request: dates, location, reason, status and who has to approve it, with Cancel while it is still
// pending. Opened from a WFH row in My workspace (Attendance and Requests tabs). The employee can only cancel a request
// that has not been decided yet (the server enforces this and reports it as `can_cancel`); an approved one cannot be
// cancelled from here, so the dialog says so instead of leaving the person looking for a button that does not exist.

import { useState } from "react";
import Modal from "@/components/Modal";
import { confirmDialog } from "@/components/DialogProvider";
import { useToast } from "@/components/ToastProvider";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import { WFH_STATUS_LABELS, type WorkFromHomeRequest } from "@/types/workFromHome";
import { STATUS_BADGE_CLASS, fmtSubmitted, toDisplayStatus } from "../../my-requests/_data";

interface WfhRequestDetailModalProps {
  request: WorkFromHomeRequest;
  onClose: () => void;
  /** Called after the request was cancelled, so the host can refresh its WFH list. */
  onChanged: () => void;
  /** An admin viewing someone else's workspace: a cancel would be sent as the admin and refused, so the button is hidden. */
  readOnly?: boolean;
}

const MS_PER_DAY = 86_400_000;

function day(iso: string): string {
  return iso ? formatDate(`${iso}T12:00:00`) : "";
}

function dayCount(request: WorkFromHomeRequest): number {
  return Math.round((new Date(request.end_date).getTime() - new Date(request.start_date).getTime()) / MS_PER_DAY) + 1;
}

function StageRow({ label, approverName, status, remarks }: {
  label: string; approverName: string; status: "approved" | "rejected" | null; remarks: string;
}) {
  const badge = status === "approved" ? "badge badge-success" : status === "rejected" ? "badge badge-error" : "badge badge-warn";
  const text = status === "approved" ? "Approved" : status === "rejected" ? "Rejected" : "Pending";
  return (
    <div className="flex items-start justify-between gap-3 py-2 border-b border-[var(--outline-v)] last:border-b-0">
      <div>
        <div className="text-sm font-medium text-[var(--on-bg)]">{label}</div>
        <div className="text-xs text-[var(--on-variant)] mt-0.5">{approverName || "Not yet assigned"}</div>
        {remarks && <div className="text-xs text-[var(--on-variant)] bg-[var(--bg-low)] rounded-md px-2 py-1 mt-1.5">&ldquo;{remarks}&rdquo;</div>}
      </div>
      <span className={badge}>{text}</span>
    </div>
  );
}

export default function WfhRequestDetailModal({ request, onClose, onChanged, readOnly = false }: WfhRequestDetailModalProps) {
  const { showToast } = useToast();
  const [cancelling, setCancelling] = useState(false);
  const days = dayCount(request);

  async function cancelRequest() {
    if (!(await confirmDialog("Cancel this work-from-home request?"))) return;
    setCancelling(true);
    try {
      const response = await clientApi.patch<{ message?: string }>(API.workFromHome.requestDetail(request.id));
      showToast(response.data.message || "Work from home request cancelled.", "success");
      onChanged();
      onClose();
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(message || "Failed to cancel request.", "error");
    } finally {
      setCancelling(false);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-home-2" style={{ marginRight: 8 }} />Work from home request</>}
      onClose={onClose}
      closeDisabled={cancelling}
      maxWidth="min(480px, 95vw)"
      footer={
        <>
          {request.can_cancel && !readOnly && (
            <button className="btn btn-ghost" type="button" onClick={cancelRequest} disabled={cancelling}>
              {cancelling ? "Cancelling…" : "Cancel request"}
            </button>
          )}
          <button className="btn btn-ghost" type="button" onClick={onClose} disabled={cancelling}>Close</button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Dates</p>
            <p className="text-sm font-medium text-[var(--on-bg)]">
              {day(request.start_date)} → {day(request.end_date)} · {days} day{days === 1 ? "" : "s"}
            </p>
          </div>
          <span className={STATUS_BADGE_CLASS[toDisplayStatus(request.status)]}>{WFH_STATUS_LABELS[request.status]}</span>
        </div>

        {request.location_label && (
          <div className="border-t border-[var(--outline-v)] pt-4">
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Location</p>
            <p className="text-sm text-[var(--on-bg)]">{request.location_label}</p>
          </div>
        )}

        {request.status === "approved" && request.enforce_location !== undefined && (
          <div className="border-t border-[var(--outline-v)] pt-4">
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Location check</p>
            <p className="text-sm text-[var(--on-bg)]">
              {request.enforce_location
                ? "You must punch near this location. If you have moved, ask your manager or HR to allow punching from any location."
                : `You can punch from any location on these days${request.location_unlocked_by_name ? ` (allowed by ${request.location_unlocked_by_name})` : ""}.`}
            </p>
          </div>
        )}

        <div className="border-t border-[var(--outline-v)] pt-4">
          <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Reason</p>
          <p className="text-sm text-[var(--on-bg)]">{request.reason || "—"}</p>
        </div>

        <div className="border-t border-[var(--outline-v)] pt-3">
          <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Approval Trail</p>
          <StageRow label="Manager Approval" approverName={request.l1_approver_name} status={request.l1_status} remarks={request.l1_remarks} />
          {request.l2_approver_name && (
            <StageRow label="HR Approval" approverName={request.l2_approver_name} status={request.l2_status} remarks={request.l2_remarks} />
          )}
        </div>

        {request.status === "approved" && (
          <p className="text-xs text-[var(--on-variant)] bg-[var(--bg-low)] rounded-md px-3 py-2">
            An approved request can&apos;t be cancelled from here. If your plans changed, ask your manager or HR.
          </p>
        )}

        <div className="text-xs text-[var(--on-variant)] border-t border-[var(--outline-v)] pt-3">
          Submitted {fmtSubmitted(request.created_at)}
        </div>
      </div>
    </Modal>
  );
}
