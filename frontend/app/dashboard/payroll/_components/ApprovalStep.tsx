"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { PayrollCycle, PayrollSettings } from "@/types/payroll";

interface Props {
  cycleId: string;
  settings: PayrollSettings | null;
  onNext: () => void;
  onBack: () => void;
}

export default function ApprovalStep({ cycleId, settings, onNext, onBack }: Props) {
  const { data: cycle, loading, refetch } = useFetch<PayrollCycle>(API.payroll.cycle(cycleId));
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [showReject, setShowReject] = useState(false);
  const [rejectNote, setRejectNote] = useState("");

  const approvalLevels = settings?.approval_levels ?? "L1";
  const isL1L2 = approvalLevels === "L1_L2";

  const isL1Done = !!cycle?.attendance_l1_approved_at;
  const isL2Done = !!cycle?.attendance_l2_approved_at;
  const isApproved = cycle?.status === "attendance_approved";

  const canApproveL1 = !isL1Done && (cycle?.status === "draft" || cycle?.status === "attendance_pending");
  const canApproveL2 = isL1Done && !isL2Done && isL1L2 && cycle?.status === "attendance_pending";

  async function approve(level: "L1" | "L2") {
    setBusy(true);
    setErr(null);
    try {
      await clientApi.post(API.payroll.approveAttendance(cycleId), { level, comment });
      setComment("");
      refetch();
    } catch (error: unknown) {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? "Failed to approve. Check your permissions.";
      setErr(msg);
    } finally {
      setBusy(false);
    }
  }

  function fmt(dateStr: string | null | undefined) {
    if (!dateStr) return null;
    return new Date(dateStr).toLocaleString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }

  if (loading) {
    return (
      <div className="card" style={{ padding: "40px", textAlign: "center", color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 28 }} />
        <div style={{ marginTop: 8 }}>Loading approval status…</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-user-check" /> Attendance Approval Gate</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {isApproved && <span className="badge badge-success"><i className="ti ti-check" /> Approved</span>}
          {!isApproved && <span className="badge badge-warn"><i className="ti ti-clock" /> Pending</span>}
          <span className="badge badge-info">{isL1L2 ? "L1 + L2 required" : "L1 only"}</span>
        </div>
      </div>
      <div className="card-body">

        <div className="alert alert-info" style={{ marginBottom: 20 }}>
          <i className="ti ti-info-circle" />
          <span>Attendance data must be approved before payroll can be processed. This ensures salary calculations are based on verified attendance.</span>
        </div>

        {err && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>
            <i className="ti ti-alert-circle" />
            <span>{err}</span>
          </div>
        )}

        {isApproved && (
          <div className="alert alert-success" style={{ marginBottom: 20 }}>
            <i className="ti ti-circle-check" />
            <span>Attendance approved. You can now proceed to compute payroll.</span>
          </div>
        )}

        {/* Workflow */}
        <div style={{ display: "flex", flexDirection: "column", gap: 0, marginBottom: 24 }}>

          {/* L1 approval */}
          <ApprovalCard
            level="L1"
            title="Manager Approval (L1)"
            subtitle="Direct manager verifies attendance records"
            isDone={isL1Done}
            isCurrent={canApproveL1}
            approverName={cycle?.l1_approver_name}
            doneAt={fmt(cycle?.attendance_l1_approved_at)}
            isLast={!isL1L2}
            comment={comment}
            onCommentChange={setComment}
            onApprove={() => approve("L1")}
            busy={busy}
          />

          {isL1L2 && (
            <ApprovalCard
              level="L2"
              title="HR Approval (L2)"
              subtitle="HR verifies and signs off on attendance"
              isDone={isL2Done}
              isCurrent={canApproveL2}
              approverName={cycle?.l2_approver_name}
              doneAt={fmt(cycle?.attendance_l2_approved_at)}
              isLast
              comment={comment}
              onCommentChange={setComment}
              onApprove={() => approve("L2")}
              busy={busy}
            />
          )}
        </div>
      </div>

      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "space-between", gap: 10 }}>
        <div>
          {cycle && (
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Cycle: {cycle.cycle_start} → {cycle.cycle_end} · Pay date: {cycle.pay_date}
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
          <button
            className="btn btn-filled"
            onClick={onNext}
            disabled={!isApproved}
            style={{ opacity: isApproved ? 1 : 0.5 }}
          >
            Continue <i className="ti ti-arrow-right" />
          </button>
        </div>
      </div>

      {showReject && (
        <div className="modal-overlay open" onClick={() => setShowReject(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title" style={{ color: "var(--error)" }}><i className="ti ti-alert-circle" /> Reject</div>
              <button className="modal-close" onClick={() => setShowReject(false)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              <div className="field-group">
                <label className="field-label">Rejection Reason *</label>
                <textarea className="field-input" placeholder="State the reason…" value={rejectNote} onChange={e => setRejectNote(e.target.value)} style={{ height: 100 }} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowReject(false)}>Cancel</button>
              <button className="btn btn-danger" disabled={!rejectNote.trim()}>Confirm Reject</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sub-component ──────────────────────────────────────────────────────────────

interface ApprovalCardProps {
  level: "L1" | "L2";
  title: string;
  subtitle: string;
  isDone: boolean;
  isCurrent: boolean;
  approverName: string | null | undefined;
  doneAt: string | null;
  isLast: boolean;
  comment: string;
  onCommentChange: (v: string) => void;
  onApprove: () => void;
  busy: boolean;
}

function ApprovalCard({
  level, title, subtitle, isDone, isCurrent,
  approverName, doneAt, isLast,
  comment, onCommentChange, onApprove, busy,
}: ApprovalCardProps) {
  const dotColor = isDone ? "var(--success)" : isCurrent ? "var(--warn)" : "var(--outline)";
  const icon     = isDone ? "ti-circle-check" : isCurrent ? "ti-clock" : "ti-circle-dashed";

  return (
    <div style={{ display: "flex", gap: 0 }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 40, flexShrink: 0 }}>
        <div style={{
          width: 36, height: 36, borderRadius: "50%", background: dotColor,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", flexShrink: 0,
          boxShadow: isCurrent ? "0 0 0 4px var(--warn-c)" : "none",
        }}>
          <i className={`ti ${icon}`} style={{ fontSize: 16 }} />
        </div>
        {!isLast && (
          <div style={{ width: 2, flex: 1, minHeight: 20, background: isDone ? "var(--success)" : "var(--outline-v)", margin: "4px 0" }} />
        )}
      </div>

      <div style={{
        flex: 1, marginLeft: 14, marginBottom: 20,
        padding: "14px 16px",
        border: `1.5px solid ${isCurrent ? "var(--warn)" : isDone ? "var(--success)" : "var(--outline-v)"}`,
        borderRadius: "var(--radius)",
        background: isCurrent ? "var(--warn-c)" : "transparent",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{subtitle}</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {doneAt && <span style={{ fontSize: 11, color: "var(--on-variant)" }}>{doneAt}</span>}
            <span className={isDone ? "badge badge-success" : isCurrent ? "badge badge-warn" : "badge badge-neutral"}>
              {isDone ? "Approved" : isCurrent ? "Pending" : "Waiting"}
            </span>
          </div>
        </div>

        {approverName && (
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
            Approved by: <strong>{approverName}</strong>
          </div>
        )}

        {isCurrent && (
          <div style={{ marginTop: 12 }}>
            <textarea
              className="field-input"
              placeholder="Add approval note (optional)…"
              value={comment}
              onChange={e => onCommentChange(e.target.value)}
              style={{ resize: "none", height: 65, marginBottom: 10, fontSize: 13 }}
            />
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="btn btn-success btn-sm"
                onClick={onApprove}
                disabled={busy}
              >
                {busy
                  ? <><i className="ti ti-loader-2 animate-spin" /> Approving…</>
                  : <><i className="ti ti-check" /> Approve {level}</>}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
