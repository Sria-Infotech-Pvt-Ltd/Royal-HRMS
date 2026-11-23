"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { LeaveRequest, STATUS_BADGE, STATUS_LABEL, fmtDate } from "../_data";
import LeaveCancellationPanel from "./LeaveCancellationPanel";
import Modal from "@/components/Modal";

interface Props {
  requestId:        string;
  initialData:      LeaveRequest;
  onClose:          () => void;
  onApprove?:       () => void;
  onReject?:        () => void;
  onCancelRequest?: () => void;
  /** Called after a cancellation request / decision so the list can refresh. */
  onChanged?:       () => void;
}

const DECISION_LABEL: Record<string, string> = {
  approved: "Approved",
  rejected: "Rejected",
};

function DecisionRow({
  level, approverName, decisionStatus, remarks, actionedAt,
}: {
  level:          string;
  approverName:   string;
  decisionStatus: string | null;
  remarks:        string;
  actionedAt:     string | null;
}) {
  const label = decisionStatus ? (DECISION_LABEL[decisionStatus] ?? decisionStatus) : "Pending";
  const dotClass = decisionStatus === "approved" ? "bg-green-500" : decisionStatus === "rejected" ? "bg-red-500" : "bg-amber-400";

  return (
    <div className="flex gap-3">
      <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${dotClass}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold text-[var(--on-bg)]">{level}</span>
          <span className="text-xs font-medium text-[var(--on-variant)]">{label}</span>
        </div>
        <p className="text-xs text-[var(--on-variant)] mt-0.5">{approverName || "Not yet assigned"}</p>
        {remarks && (
          <p className="text-xs text-[var(--on-variant)] bg-[var(--bg-low)] rounded-lg px-2.5 py-1.5 mt-1.5">“{remarks}”</p>
        )}
        {actionedAt && (
          <p className="text-xs text-[var(--on-variant)] mt-1">{fmtDate(actionedAt.slice(0, 10))}</p>
        )}
      </div>
    </div>
  );
}

export default function LeaveRequestDetailModal({
  requestId, initialData, onClose, onApprove, onReject, onCancelRequest, onChanged,
}: Props) {
  // Row data renders immediately (no blank flash); GET /leave/requests/<id>/
  // then supplies the current state in case it changed since the list loaded.
  const { data, loading, error, refetch } = useFetch<LeaveRequest>(API.leave.requestDetail(requestId));
  const r = data ?? initialData;

  // Uses the shared Modal (same white card, header, close button and footer as
  // every other popup in the app).
  const title = (
    <div className="flex items-center gap-3">
      <div className="w-9 h-9 rounded-xl bg-[var(--info-c)] flex items-center justify-center flex-shrink-0">
        <i className="ti ti-file-description text-[var(--info)] text-lg" />
      </div>
      <div>
        <div>Leave Request Details</div>
        <p className="text-xs font-normal text-[var(--on-variant)] mt-0.5">{r.leave_type_display} · {r.duration_display}</p>
      </div>
    </div>
  );

  const footer = (
    <>
      <button className="btn btn-ghost" onClick={onClose}>Close</button>
      {/* This list only ever contains the caller's own requests, so status is
          a safe stand-in on rows the backend hasn't attached can_cancel to. */}
      {onCancelRequest && (r.can_cancel ?? (r.status === "pending" || r.status === "l2_pending")) && (
        <button
          className="btn btn-outline"
          style={{ color: "var(--error)", borderColor: "var(--error)" }}
          onClick={() => {
            if (window.confirm("Are you sure you want to cancel this leave request?")) {
              onCancelRequest();
              onClose();
            }
          }}
        >
          Cancel Request
        </button>
      )}
      {/* onApprove/onReject are only ever passed from an approval-queue context,
          which the backend already scopes to actionable rows — true otherwise. */}
      {onReject && (r.can_approve ?? true) && (
        <button className="btn btn-danger" onClick={() => { onReject(); onClose(); }}>
          <i className="ti ti-x" /> Reject
        </button>
      )}
      {onApprove && (r.can_approve ?? true) && (
        <button className="btn btn-success" onClick={() => { onApprove(); onClose(); }}>
          <i className="ti ti-check" /> Approve
        </button>
      )}
    </>
  );

  return (
    <Modal title={title} onClose={onClose} footer={footer} maxWidth={480} scrollBody>
        <div className="flex flex-col gap-5">

          {loading && !data && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--on-variant)]">
              <i className="ti ti-loader-2 animate-spin" /> Loading latest status…
            </div>
          )}
          {error && (
            <div className="flex items-center gap-1.5 text-xs text-red-500">
              <i className="ti ti-alert-circle" /> Could not refresh — showing last known details.
            </div>
          )}

          <div>
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Employee</p>
            <p className="text-sm text-[var(--on-bg)] font-medium">{r.employee_name}</p>
            <p className="text-xs text-[var(--on-variant)] mt-0.5">
              {[r.employee_code, r.employee_dept, r.employee_branch].filter(Boolean).join(" · ") || "—"}
            </p>
          </div>

          <div className="flex items-start justify-between border-t border-[var(--outline-v)] pt-4">
            <div className="text-xs text-[var(--on-variant)]">
              <p>{fmtDate(r.start_date)} → {fmtDate(r.end_date)}</p>
              {r.lop_days > 0 ? (
                <div className="mt-1.5 flex flex-col gap-0.5">
                  <span>{r.leave_type_display}: {r.total_days - r.lop_days} day{(r.total_days - r.lop_days) !== 1 ? "s" : ""}</span>
                  <span className="text-amber-600 font-medium">LOP: {r.lop_days} day{r.lop_days !== 1 ? "s" : ""}</span>
                  <span className="text-[var(--on-bg)] font-semibold">Total: {r.total_days} day{r.total_days !== 1 ? "s" : ""}</span>
                </div>
              ) : (
                <span>{r.total_days} day{r.total_days !== 1 ? "s" : ""}</span>
              )}
            </div>
            <span className={STATUS_BADGE[r.status]}>{STATUS_LABEL[r.status]}</span>
          </div>

          <div>
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Reason</p>
            <p className="text-sm text-[var(--on-bg)]">{r.reason || "—"}</p>
          </div>

          <div className="flex items-center justify-between border-t border-[var(--outline-v)] pt-4">
            <div>
              <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1">Approver</p>
              <p className="text-sm text-[var(--on-bg)] font-medium">{r.approved_by || "—"}</p>
            </div>
            <p className="text-xs text-[var(--on-variant)]">
              {r.approved_at ? fmtDate(r.approved_at.slice(0, 10)) : "Not yet actioned"}
            </p>
          </div>

          <div className="flex flex-col gap-4 border-t border-[var(--outline-v)] pt-4">
            <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide -mb-1">Approval Flow</p>
            <DecisionRow
              level="Manager Approval"
              approverName={r.l1_approver_name}
              decisionStatus={r.l1_status}
              remarks={r.l1_remarks}
              actionedAt={r.l1_actioned_at}
            />
            {r.l2_approver_name && (
              <DecisionRow
                level="HR Approval"
                approverName={r.l2_approver_name}
                decisionStatus={r.l2_status}
                remarks={r.l2_remarks}
                actionedAt={r.l2_actioned_at}
              />
            )}
          </div>

          {(r.handover_to || r.contact_during_leave || r.handover_notes) && (
            <div className="border-t border-[var(--outline-v)] pt-4">
              <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide mb-1.5">Handover & Contact</p>
              {r.handover_to && <p className="text-sm text-[var(--on-bg)]">Handover to: <span className="font-medium">{r.handover_to}</span></p>}
              {r.contact_during_leave && <p className="text-sm text-[var(--on-bg)] mt-0.5">Contact: <span className="font-medium">{r.contact_during_leave}</span></p>}
              {r.handover_notes && <p className="text-xs text-[var(--on-variant)] mt-1.5">{r.handover_notes}</p>}
            </div>
          )}

          <LeaveCancellationPanel request={r} onChanged={() => { refetch(); onChanged?.(); }} />

          {r.document_url && (
            <div className="border-t border-[var(--outline-v)] pt-4">
              <a
                href={r.document_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-[var(--primary)] hover:opacity-80 font-medium"
              >
                <i className="ti ti-paperclip" /> View attached document
              </a>
            </div>
          )}
        </div>
    </Modal>
  );
}
