"use client";

import { useState, type CSSProperties } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { isUnrestrictedUser } from "@/lib/auth";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import type { FaceRegistrationDecisionPayload, FaceRegistrationRequest, PaginatedFaceRegistrations } from "@/types/faceRegistration";
import RejectReasonModal from "./RejectReasonModal";
import { PersonAvatar, TabEmpty, TabHeader } from "./ApprovalTabChrome";
import { ApprovalTabStyles } from "./approvalTabStyles";

function fmtDate(dateStr: string): string {
  if (!dateStr) return "—";
  return formatDate(dateStr);
}

function fmtScore(score: number | null): string {
  return score === null ? "—" : `${Math.round(score * 100)}%`;
}

export default function FaceRegistrationApprovalsTab() {
  const canReview = usePermission("facial_recognition.approve");
  // A full-access user (superuser or settings.edit) always sees every request in every branch, so the "only mine" narrowing is hidden for them.
  const isFullAccess = isUnrestrictedUser(useCurrentUser());
  const [page, setPage] = useState(1);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [rowError, setRowError] = useState<{ id: string; message: string } | null>(null);
  const [rejecting, setRejecting] = useState<FaceRegistrationRequest | null>(null);
  const [rejectError, setRejectError] = useState("");
  const [isAssignedOnly, setIsAssignedOnly] = useState(false);

  const listUrl = `${API.attendance.faceRegistration.pending}?page=${page}&page_size=20${isAssignedOnly && !isFullAccess ? "&assigned_to_me=1" : ""}`;
  const { data, loading, error, status, refetch } = useFetch<PaginatedFaceRegistrations>(listUrl);
  const rows = data?.results ?? [];
  const failedCount = rows.filter(row => !row.liveness_passed).length;

  function reviewErrorMessage(err: unknown): string {
    return (err as { response?: { data?: { message?: string } }; message?: string })
      ?.response?.data?.message ?? (err as { message?: string })?.message ?? "Failed to review request.";
  }

  async function handleReview(id: string, decision: FaceRegistrationDecisionPayload["status"], notes?: string) {
    setReviewingId(id);
    setRowError(null);
    setRejectError("");
    try {
      await clientApi.patch(API.attendance.faceRegistration.review(id), notes ? { status: decision, notes } : { status: decision });
      setRejecting(null);
      refetch();
    } catch (err: unknown) {
      // A rejection keeps its dialog (and the typed reason) open and shows the server's message there.
      if (decision === "rejected") setRejectError(reviewErrorMessage(err));
      else setRowError({ id, message: reviewErrorMessage(err) });
    } finally {
      setReviewingId(null);
    }
  }

  // A 403 here means the signed-in user simply doesn't hold facial_recognition.approve —
  // distinct from "genuinely zero pending requests" (see hooks/useFetch.ts's status field).
  if (status === 403) {
    return (
      <div className="alert alert-error">
        <i className="ti ti-lock" /> You don&apos;t have permission to review face registration requests.
      </div>
    );
  }

  return (
    <>
      {error && status !== 403 && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      <ApprovalTabStyles />
      <div className="card" style={{ overflow: "hidden" }}>
        <TabHeader
          icon="ti-face-id" accent="#0d9488" title="Face registration" subtitle="Check each employee's face scan before they can use Face ID for attendance."
          stats={[
            { label: "Waiting", value: rows.length, icon: "ti-hourglass", accent: "#d97706", isUrgent: rows.length > 0 },
            { label: "Liveness failed", value: failedCount, icon: "ti-alert-triangle", accent: "#dc2626" },
          ]}
          actions={isFullAccess ? undefined : (
            <label className={`tb-switch${isAssignedOnly ? " is-on" : ""}`}>
              <input type="checkbox" checked={isAssignedOnly} onChange={event => { setIsAssignedOnly(event.target.checked); setPage(1); }} />
              Only employees assigned to me
            </label>
          )}
        />
        <div className="table-wrap">
          <table className="tb-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Liveness</th>
                <th>Score</th>
                <th>Submitted</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={5} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={5}><TabEmpty icon="ti-checks" title="No pending face registration requests." hint="New face scans from employees appear here for your review." /></td></tr>
              )}
              {rows.map(r => (
                <tr key={r.id}>
                  <td>
                    <div className="tb-person">
                      <PersonAvatar name={r.employee_name} />
                      <div>
                        <div style={{ fontWeight: 600 }}>{r.employee_name}</div>
                        <div className="tb-sub">
                          {r.employee_code || "No employee ID"}{r.branch_name ? ` · ${r.branch_name}` : ""}
                        </div>
                        <div className="tb-sub">{r.employee_email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${r.liveness_passed ? "badge-success" : "badge-error"}`}>
                      {r.liveness_passed ? "Passed" : "Failed"}
                    </span>
                  </td>
                  <td>
                    <div className="tb-score" style={{ "--tb-meter": r.liveness_passed ? "#16a34a" : "#dc2626" } as CSSProperties}>
                      <div className="tb-meter" aria-hidden="true"><i style={{ width: `${Math.round((r.liveness_score ?? 0) * 100)}%` }} /></div>
                      <span>{fmtScore(r.liveness_score)}</span>
                    </div>
                  </td>
                  <td>{fmtDate(r.created_at)}</td>
                  <td>
                    {canReview ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <button
                            className="btn btn-outline btn-sm"
                            style={{ padding: "3px 10px", fontSize: 11, color: "var(--success)" }}
                            disabled={reviewingId === r.id}
                            onClick={() => handleReview(r.id, "approved")}
                          >
                            <i className="ti ti-check" /> Approve
                          </button>
                          <button
                            className="btn btn-outline btn-sm"
                            style={{ padding: "3px 10px", fontSize: 11, color: "var(--error)" }}
                            disabled={reviewingId === r.id}
                            onClick={() => { setRejectError(""); setRejecting(r); }}
                          >
                            <i className="ti ti-x" /> Reject
                          </button>
                        </div>
                        {rowError?.id === r.id && (
                          <span style={{ fontSize: 11, color: "var(--error)" }}>{rowError.message}</span>
                        )}
                      </div>
                    ) : (
                      <span style={{ fontSize: 11, color: "var(--on-variant)" }}>Awaiting an approver</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data && data.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {data.page} of {data.total_pages}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= data.total_pages} onClick={() => setPage(p => Math.min(p + 1, data.total_pages))}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>

      {rejecting && (
        <RejectReasonModal
          employeeName={rejecting.employee_name}
          isSaving={reviewingId === rejecting.id}
          serverError={rejectError}
          onSubmit={remarks => handleReview(rejecting.id, "rejected", remarks)}
          onCancel={() => { setRejecting(null); setRejectError(""); }}
        />
      )}
    </>
  );
}
