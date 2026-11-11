"use client";

// Approvals → Leave Cancellations: employees asking to cancel an already
// approved leave. Approving cancels it and returns the days to the balance;
// rejecting (reason required) keeps the leave approved.

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { apiMessage, rejectRemarksError } from "@/lib/approvalWorkflows";
import { fmtDate, type LeaveRequest } from "@/app/dashboard/leave/_data";

export default function LeaveCancellationsSection() {
  const { data, loading, error, refetch } = useFetch<LeaveRequest[]>(API.leave.cancellations);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [remarks, setRemarks] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function decide(r: LeaveRequest, action: "approve" | "reject") {
    if (action === "reject" && rejectRemarksError(remarks)) return;
    if (action === "approve" && !window.confirm(`Cancel ${r.employee_name}'s approved leave and return the days?`)) return;
    setBusy(r.id);
    setMsg(null);
    try {
      await clientApi.post(API.leave.cancellationDecision(r.id), { action, remarks: action === "reject" ? remarks : "" });
      setMsg({ ok: true, text: action === "approve" ? "Leave cancelled and balance restored." : "Cancellation rejected." });
      setRejecting(null);
      setRemarks("");
      refetch();
    } catch (err) {
      setMsg({ ok: false, text: apiMessage(err, "Failed to save the decision.") });
    } finally {
      setBusy(null);
    }
  }

  const rows = data ?? [];
  return (
    <div className="settings-card" data-testid="leave-cancellations">
      <div style={{ fontWeight: 600, fontSize: 15 }}>Leave cancellation requests</div>
      <div className="text-[12px] text-[var(--on-variant)] mt-1 mb-3">
        Approved leave the employee wants to cancel before it starts.
      </div>
      {msg && <div className={`alert ${msg.ok ? "alert-success" : "alert-error"} mb-3`}>{msg.text}</div>}
      {loading && <div className="text-[13px] text-[var(--on-variant)]">Loading…</div>}
      {error && <div className="alert alert-error">{error}</div>}
      {!loading && !error && rows.length === 0 && (
        <div className="text-[13px] text-[var(--on-variant)] py-3">No cancellation requests waiting for you.</div>
      )}
      {rows.map(r => (
        <div key={r.id} style={{ borderTop: "1px solid var(--outline-v)", padding: "12px 0" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{r.employee_name} <span className="text-[var(--on-variant)] font-normal">({r.employee_code})</span></div>
              <div className="text-[12px] text-[var(--on-variant)]">
                {r.leave_type_display} · {fmtDate(r.start_date)} – {fmtDate(r.end_date)} · {r.total_days} day(s)
              </div>
              <div className="text-[12px] mt-1">Reason: “{r.cancellation_reason}”</div>
            </div>
            {rejecting !== r.id && (
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <button className="btn btn-ghost" disabled={busy === r.id} onClick={() => { setRejecting(r.id); setRemarks(""); }}>
                  Reject
                </button>
                <button className="btn btn-primary" disabled={busy === r.id} onClick={() => decide(r, "approve")}>
                  Approve cancellation
                </button>
              </div>
            )}
          </div>
          {rejecting === r.id && (
            <div style={{ marginTop: 10 }}>
              <label className="field-label" htmlFor={`rej-${r.id}`}>Reason for rejecting *</label>
              <textarea id={`rej-${r.id}`} className="field-input" rows={2} value={remarks}
                        onChange={e => setRemarks(e.target.value)} />
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 8 }}>
                <button className="btn btn-ghost" onClick={() => setRejecting(null)}>Back</button>
                <button className="btn btn-primary" disabled={busy === r.id || !!rejectRemarksError(remarks)}
                        onClick={() => decide(r, "reject")}>
                  Reject cancellation
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
