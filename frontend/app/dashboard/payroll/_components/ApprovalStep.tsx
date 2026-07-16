"use client";

import { useState } from "react";

interface Props { onNext: () => void; onBack: () => void; }

type ApprovalStatus = "pending" | "approved" | "rejected" | "sent_back";

interface Approver {
  role:    string;
  name:    string;
  avatar:  string;
  dept:    string;
  status:  ApprovalStatus;
  comment: string;
  date:    string;
}

const WORKFLOW: Approver[] = [
  { role: "HR Manager",      name: "Rajan Pillai",   avatar: "RP", dept: "Human Resources", status: "approved", comment: "All documents verified. Approved for June 2026.", date: "29 Jun 2026, 10:32 AM" },
  { role: "Finance Manager", name: "Divya Krishnan", avatar: "DK", dept: "Finance",          status: "pending",  comment: "", date: "" },
  { role: "Management",      name: "CEO Office",     avatar: "CE", dept: "Executive",        status: "pending",  comment: "", date: "" },
];

const STATUS_STYLE: Record<ApprovalStatus, { badge: string; icon: string; dot: string }> = {
  approved:  { badge: "badge badge-success", icon: "ti-circle-check",  dot: "var(--success)" },
  pending:   { badge: "badge badge-warn",    icon: "ti-clock",          dot: "var(--warn)"    },
  rejected:  { badge: "badge badge-error",   icon: "ti-circle-x",      dot: "var(--error)"   },
  sent_back: { badge: "badge badge-neutral", icon: "ti-corner-up-left", dot: "var(--outline)" },
};

export default function ApprovalStep({ onNext, onBack }: Props) {
  const [workflow, setWorkflow] = useState<Approver[]>(WORKFLOW);
  const [comment, setComment]   = useState("");
  const [showReject, setShowReject] = useState(false);
  const [rejectNote, setRejectNote] = useState("");

  const currentIdx = workflow.findIndex(a => a.status === "pending");
  const allApproved = workflow.every(a => a.status === "approved");

  function approve() {
    if (currentIdx < 0) return;
    setWorkflow(prev => prev.map((a, i) => i === currentIdx
      ? { ...a, status: "approved", comment: comment || "Approved", date: "30 Jun 2026, 11:15 AM" }
      : a
    ));
    setComment("");
  }

  function reject() {
    if (currentIdx < 0 || !rejectNote.trim()) return;
    setWorkflow(prev => prev.map((a, i) => i === currentIdx
      ? { ...a, status: "rejected", comment: rejectNote, date: "30 Jun 2026, 11:15 AM" }
      : a
    ));
    setShowReject(false);
    setRejectNote("");
  }

  function sendBack() {
    if (currentIdx < 0) return;
    setWorkflow(prev => prev.map((a, i) => i === currentIdx
      ? { ...a, status: "sent_back", comment: "Sent back for revision", date: "30 Jun 2026, 11:15 AM" }
      : a
    ));
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-user-check" /> Payroll Approval</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {allApproved && <span className="badge badge-success"><i className="ti ti-check" /> Fully Approved</span>}
          <span className="badge badge-info">Step 9 of 11</span>
        </div>
      </div>
      <div className="card-body">

        {allApproved && (
          <div className="alert alert-success" style={{ marginBottom: 20 }}>
            <i className="ti ti-circle-check" />
            <span>All approval levels completed. Ready to generate payslips.</span>
          </div>
        )}

        {/* Workflow visual */}
        <div style={{ display: "flex", flexDirection: "column", gap: 0, marginBottom: 24 }}>
          {workflow.map((approver, idx) => {
            const style = STATUS_STYLE[approver.status];
            const isCurrent = idx === currentIdx;
            return (
              <div key={idx} style={{ display: "flex", gap: 0 }}>
                {/* Left connector */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 40, flexShrink: 0 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: "50%", background: style.dot,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: "#fff", fontSize: 16, fontWeight: 700, flexShrink: 0,
                    border: isCurrent ? `3px solid var(--warn-c)` : "none",
                    boxShadow: isCurrent ? "0 0 0 3px var(--warn-c)" : "none",
                  }}>
                    <i className={`ti ${style.icon}`} style={{ fontSize: 16 }} />
                  </div>
                  {idx < workflow.length - 1 && (
                    <div style={{ width: 2, flex: 1, minHeight: 20, background: idx < currentIdx ? "var(--success)" : "var(--outline-v)", margin: "4px 0" }} />
                  )}
                </div>

                {/* Card */}
                <div style={{
                  flex: 1, marginLeft: 14, marginBottom: 20,
                  padding: "14px 16px", border: `1.5px solid ${isCurrent ? "var(--warn)" : "var(--outline-v)"}`,
                  borderRadius: "var(--radius)", background: isCurrent ? "var(--warn-c)" : "#fff",
                }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 30, height: 30, borderRadius: "50%", background: style.dot, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}>{approver.avatar}</div>
                      <div>
                        <div style={{ fontWeight: 600 }}>{approver.name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{approver.role} · {approver.dept}</div>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      {approver.date && <span style={{ fontSize: 11, color: "var(--on-variant)" }}>{approver.date}</span>}
                      <span className={style.badge}>{approver.status.replace("_"," ").replace(/\b\w/g, c => c.toUpperCase())}</span>
                    </div>
                  </div>
                  {approver.comment && (
                    <div style={{ fontSize: 12, color: "var(--on-variant)", fontStyle: "italic", borderTop: "1px solid var(--outline-v)", paddingTop: 8, marginTop: 4 }}>
                      "{approver.comment}"
                    </div>
                  )}
                  {isCurrent && (
                    <div style={{ marginTop: 10 }}>
                      <textarea
                        className="field-input"
                        placeholder="Add approval comment (optional)..."
                        value={comment}
                        onChange={e => setComment(e.target.value)}
                        style={{ resize: "none", height: 70, marginBottom: 10 }}
                      />
                      <div style={{ display: "flex", gap: 8 }}>
                        <button className="btn btn-success btn-sm" onClick={approve}><i className="ti ti-check" /> Approve</button>
                        <button className="btn btn-danger btn-sm" onClick={() => setShowReject(true)}><i className="ti ti-x" /> Reject</button>
                        <button className="btn btn-ghost btn-sm" onClick={sendBack}><i className="ti ti-corner-up-left" /> Send Back</button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
        <button className="btn btn-filled" onClick={onNext} disabled={!allApproved} style={{ opacity: allApproved ? 1 : 0.5 }}>
          Continue <i className="ti ti-arrow-right" />
        </button>
      </div>

      {showReject && (
        <div className="modal-overlay open" onClick={() => setShowReject(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title" style={{ color: "var(--error)" }}><i className="ti ti-alert-circle" /> Reject Payroll</div>
              <button className="modal-close" onClick={() => setShowReject(false)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              <div className="field-group">
                <label className="field-label">Rejection Reason *</label>
                <textarea className="field-input" placeholder="State the reason for rejection..." value={rejectNote} onChange={e => setRejectNote(e.target.value)} style={{ height: 100 }} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowReject(false)}>Cancel</button>
              <button className="btn btn-danger" onClick={reject} disabled={!rejectNote.trim()}>Confirm Reject</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
