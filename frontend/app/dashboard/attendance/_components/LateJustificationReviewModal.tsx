"use client";

// Review one late-arrival justification (HR Attendance → Late Justifications,
// and Approvals). Approve / Reject / Request resubmission — a reason is
// required for the last two. The proof opens only when the server says this
// user may see it (can_view_document); managers see the reason, not the file.

import { useState } from "react";
import Modal from "@/components/Modal";
import DocPreviewModal from "@/components/DocPreviewModal";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";
import { LATE_STATUS, reviewTrail } from "@/lib/lateJustification";
import type { LateJustificationRow } from "@/types/lateJustification";

type Action = "approve" | "reject" | "resubmit";

function fmtDate(iso: string) {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
}

export default function LateJustificationReviewModal({ request, onClose, onDone }: {
  request: LateJustificationRow;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const r = request;
  const [action, setAction] = useState<Action | null>(null);
  const [remarks, setRemarks] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [preview, setPreview] = useState(false);
  const needsReason = action === "reject" || action === "resubmit";

  async function send() {
    if (!action) return;
    if (needsReason && !remarks.trim()) { setErr("Give a reason — it is shown to the employee."); return; }
    setBusy(true);
    setErr(null);
    try {
      const { data } = await clientApi.patch(API.attendance.correctionReview(r.id), { action, remarks: remarks.trim() });
      onDone((data as { message?: string })?.message ?? "Saved.");
      onClose();
    } catch (e) {
      setErr((e as { message?: string })?.message ?? "Could not save the decision.");
    } finally {
      setBusy(false);
    }
  }

  const row = (k: string, v: React.ReactNode) => (
    <div style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: 8, padding: "6px 0", borderBottom: "1px solid var(--outline-v)" }}>
      <div style={{ color: "var(--on-variant)" }}>{k}</div><div>{v}</div>
    </div>
  );
  const trail = reviewTrail(r);

  return (
    <>
      <Modal title="Late arrival justification" onClose={onClose} closeDisabled={busy} size="lg"
        footer={r.can_action ? (
          action ? (
            <>
              <button className="btn btn-ghost" onClick={() => { setAction(null); setErr(null); }} disabled={busy}>Back</button>
              <button className="btn btn-filled" onClick={send} disabled={busy}>
                {busy ? "Saving…" : action === "approve" ? "Confirm approval" : action === "reject" ? "Reject" : "Send back"}
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-ghost" onClick={() => setAction("resubmit")}><i className="ti ti-arrow-back-up" /> Request resubmission</button>
              <button className="btn btn-ghost" style={{ color: "var(--error)" }} onClick={() => setAction("reject")}><i className="ti ti-x" /> Reject</button>
              <button className="btn btn-filled" onClick={() => setAction("approve")}><i className="ti ti-check" /> Approve</button>
            </>
          )
        ) : <button className="btn btn-filled" onClick={onClose}>Close</button>}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 13 }}>
          {err && <div className="alert alert-error">{err}</div>}
          <div>
            {row("Employee", <><strong>{r.name}</strong> <span style={{ color: "var(--on-variant)" }}>{r.employee_id} · {r.branch || "—"}</span></>)}
            {row("Date", fmtDate(r.date))}
            {row("Recorded punches", <span className="font-mono">{r.original_in ?? "—"} → {r.original_out ?? "—"}</span>)}
            {row("Attendance", r.attendance_status ?? "—")}
            {row("Reason", <strong>{r.reason_label}</strong>)}
            {row("Explanation", <span style={{ whiteSpace: "pre-wrap" }}>{r.explanation}</span>)}
            {row("Proof", r.has_document
              ? (r.can_view_document
                ? <button className="btn btn-ghost btn-sm" onClick={() => setPreview(true)}><i className="ti ti-file" /> View {r.document_name || "proof"}</button>
                : <span style={{ color: "var(--on-variant)" }}><i className="ti ti-lock" /> Attached — visible to authorised HR only</span>)
              : <span style={{ color: r.proof_required ? "var(--error)" : "var(--on-variant)" }}>{r.proof_required ? "Missing (required for medical)" : "None"}</span>)}
            {row("Status", <span className={LATE_STATUS[r.status].cls}>{r.status === "approved" ? "Approved — Late (Excused)" : LATE_STATUS[r.status].label}</span>)}
            {r.resubmission_count > 0 && row("Resubmissions", r.resubmission_count)}
            {trail.length > 0 && row("Decisions", <>{trail.map(t => <div key={t}>{t}</div>)}</>)}
          </div>

          {action === "approve" && (
            <div className="alert alert-info">
              {r.status === "pending" && r.l2_approver_name
                ? "Your approval sends this to HR. The day is excused only after the final approval."
                : "The day will show as Late (Excused) and won't count as a late mark. Punch times stay as recorded."}
            </div>
          )}
          {needsReason && (
            <div className="field-group">
              <label className="field-label">{action === "reject" ? "Reason for rejecting" : "What should the employee change?"} <span style={{ color: "var(--error)" }}>*</span></label>
              <textarea className="field-input" style={{ minHeight: 72 }} maxLength={1000} value={remarks}
                onChange={e => setRemarks(e.target.value)} placeholder={action === "resubmit" ? "e.g. Upload the doctor's note, not the pharmacy bill" : ""} />
              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                {action === "resubmit" ? "The employee can update and resubmit within 3 days." : "This is final; the day stays an ordinary late mark."}
              </div>
            </div>
          )}
        </div>
      </Modal>
      {preview && (
        <DocPreviewModal name={`Proof — ${r.name}, ${fmtDate(r.date)}`} fileName={r.document_name}
          fileUrl={`${API_BASE}${API.attendance.correctionDocument(r.id)}`} onClose={() => setPreview(false)} />
      )}
    </>
  );
}
