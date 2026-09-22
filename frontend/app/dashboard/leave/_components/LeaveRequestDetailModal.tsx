"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { LeaveRequest, STATUS_BADGE, STATUS_LABEL, fmtDate } from "../_data";

interface Props {
  requestId:        string;
  initialData:      LeaveRequest;
  onClose:          () => void;
  onApprove?:       () => void;
  onReject?:        () => void;
  onCancelRequest?: () => void;
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
  const dotClass = decisionStatus === "approved" ? "bg-[var(--success)]" : decisionStatus === "rejected" ? "bg-[var(--error)]" : "bg-[var(--warn)]";

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
  requestId, initialData, onClose, onApprove, onReject, onCancelRequest,
}: Props) {
  // Row data renders immediately (no blank flash); GET /leave/requests/<id>/
  // then supplies the current state in case it changed since the list loaded.
  const { data, loading, error } = useFetch<LeaveRequest>(API.leave.requestDetail(requestId));
  const r = data ?? initialData;

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-[var(--surface)] rounded-2xl shadow-2xl w-full max-w-md z-10 overflow-hidden max-h-[85vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-[var(--outline-v)] flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[var(--info-c)] flex items-center justify-center flex-shrink-0">
              <i className="ti ti-file-description text-[var(--info)] text-lg" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[var(--on-bg)]">Leave Request Details</h3>
              <p className="text-xs text-[var(--on-variant)] mt-0.5">{r.leave_type_display} · {r.duration_display}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-[var(--on-variant)] hover:bg-[var(--bg-mid)] hover:text-[var(--on-bg)] transition-colors"
          >
            <i className="ti ti-x text-sm" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 overflow-y-auto flex flex-col gap-5">

          {loading && !data && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--on-variant)]">
              <i className="ti ti-loader-2 animate-spin" /> Loading latest status…
            </div>
          )}
          {error && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--error)]">
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
                  <span className="text-[var(--warn)] font-medium">LOP: {r.lop_days} day{r.lop_days !== 1 ? "s" : ""}</span>
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

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--outline-v)] flex-shrink-0">
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl border border-[var(--outline-v)] text-sm font-medium text-[var(--on-variant)] hover:bg-[var(--bg-low)] transition-colors"
          >
            Close
          </button>
          {/* This list only ever contains the caller's own requests, so status is
              a safe stand-in on rows the backend hasn't attached can_cancel to. */}
          {onCancelRequest && (r.can_cancel ?? (r.status === "pending" || r.status === "l2_pending")) && (
            <button
              onClick={() => {
                if (window.confirm("Are you sure you want to cancel this leave request?")) {
                  onCancelRequest();
                  onClose();
                }
              }}
              className="px-5 py-2.5 rounded-xl border border-[var(--error)] text-sm font-medium text-[var(--error)] hover:bg-[var(--error-c)] transition-colors"
            >
              Cancel Request
            </button>
          )}
          {/* onApprove/onReject are only ever passed from an approval-queue context,
              which the backend already scopes to actionable rows — true otherwise. */}
          {onReject && (r.can_approve ?? true) && (
            <button
              onClick={() => { onReject(); onClose(); }}
              className="btn-danger flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-colors"
            >
              <i className="ti ti-x" /> Reject
            </button>
          )}
          {onApprove && (r.can_approve ?? true) && (
            <button
              onClick={() => { onApprove(); onClose(); }}
              className="btn-success flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-colors"
            >
              <i className="ti ti-check" /> Approve
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
