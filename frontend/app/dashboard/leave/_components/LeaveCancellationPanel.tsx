"use client";

// Inside the leave detail modal: cancellation of an APPROVED leave.
//  - employee: "Request cancellation" (reason required) while the leave hasn't started
//  - approver: approve / reject (reason required) a waiting request
//  - everyone: the current cancellation status and the decision remarks

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { apiMessage, cancellationBadge, cancellationReasonError, rejectRemarksError } from "@/lib/approvalWorkflows";
import type { LeaveRequest } from "../_data";

interface Props {
  request: LeaveRequest;
  onChanged: () => void;
}

export default function LeaveCancellationPanel({ request: r, onChanged }: Props) {
  const [mode, setMode] = useState<"" | "request" | "reject">("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const { showToast } = useToast();

  const badge = cancellationBadge(r.cancellation_status);
  if (!badge && !r.can_request_cancellation) return null;

  async function submit(action: "request" | "approve" | "reject") {
    setBusy(true);
    try {
      if (action === "request") {
        await clientApi.post(API.leave.cancellationRequest(r.id), { reason: text });
      } else {
        await clientApi.post(API.leave.cancellationDecision(r.id), { action, remarks: action === "reject" ? text : "" });
      }
      showToast(action === "request" ? "Cancellation requested. You will be notified once it is decided."
        : action === "approve" ? "Cancellation approved — the days are back in the balance." : "Cancellation rejected.",
        "success");
      setMode("");
      setText("");
      onChanged();
    } catch (e) {
      showToast(apiMessage(e, "Something went wrong. Please try again."), "error");
    } finally {
      setBusy(false);
    }
  }

  const inputError = mode === "request" ? cancellationReasonError(text) : mode === "reject" ? rejectRemarksError(text) : "";

  return (
    <div className="border-t border-[var(--outline-v)] pt-4" data-testid="leave-cancellation-panel">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-[var(--on-variant)] uppercase tracking-wide">Cancellation</p>
        {badge && <span className={`badge ${badge.cls}`}>{badge.label}</span>}
      </div>
      {r.cancellation_reason && (
        <p className="text-xs text-[var(--on-variant)] mt-1.5">Reason: “{r.cancellation_reason}”</p>
      )}
      {r.cancellation_remarks && r.cancellation_status !== "requested" && (
        <p className="text-xs text-[var(--on-variant)] mt-1">Decision note: “{r.cancellation_remarks}”</p>
      )}

      {mode === "" && (
        <div className="flex gap-2 mt-3 justify-end">
          {r.can_request_cancellation && (
            <button className="btn btn-ghost" onClick={() => { setMode("request"); setText(""); }}>
              <i className="ti ti-calendar-x" /> Request cancellation
            </button>
          )}
          {r.can_decide_cancellation && (
            <>
              <button className="btn btn-ghost" disabled={busy} onClick={() => { setMode("reject"); setText(""); }}>
                Reject cancellation
              </button>
              <button className="btn btn-filled" disabled={busy} onClick={() => submit("approve")}>
                Approve cancellation
              </button>
            </>
          )}
        </div>
      )}

      {mode !== "" && (
        <div className="mt-3">
          <label className="field-label" htmlFor="lc-text">
            {mode === "request" ? "Why do you want to cancel this leave? *" : "Reason for rejecting *"}
          </label>
          <textarea id="lc-text" className="field-input" rows={2} value={text} maxLength={1000}
                    onChange={e => setText(e.target.value)} />
          {text && inputError && <p className="text-xs text-red-600 mt-1">{inputError}</p>}
          {mode === "request" && (
            <p className="text-[11px] text-[var(--on-variant)] mt-1">
              The leave stays approved until your approver accepts the cancellation; the days then return to your balance.
            </p>
          )}
          <div className="flex gap-2 mt-2 justify-end">
            <button className="btn btn-ghost" onClick={() => setMode("")}>Back</button>
            <button className="btn btn-filled" disabled={busy || !!inputError}
                    onClick={() => submit(mode === "request" ? "request" : "reject")}>
              {busy ? "Saving…" : mode === "request" ? "Send request" : "Reject"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
