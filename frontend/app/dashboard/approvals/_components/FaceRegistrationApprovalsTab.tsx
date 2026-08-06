"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { FaceRegistrationDecisionPayload, PaginatedFaceRegistrations } from "@/types/faceRegistration";

function fmtDate(dateStr: string): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function fmtScore(score: number | null): string {
  return score === null ? "—" : `${Math.round(score * 100)}%`;
}

export default function FaceRegistrationApprovalsTab() {
  const canReview = usePermission("facial_recognition.approve");
  const [page, setPage] = useState(1);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [rowError, setRowError] = useState<{ id: string; message: string } | null>(null);

  const listUrl = `${API.attendance.faceRegistration.pending}?page=${page}&page_size=20`;
  const { data, loading, error, status, refetch } = useFetch<PaginatedFaceRegistrations>(listUrl);
  const rows = data?.results ?? [];

  async function handleReview(id: string, decision: FaceRegistrationDecisionPayload["status"]) {
    setReviewingId(id);
    setRowError(null);
    try {
      await clientApi.patch(API.attendance.faceRegistration.review(id), { status: decision });
      refetch();
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { message?: string } }; message?: string })
        ?.response?.data?.message ?? (err as { message?: string })?.message ?? "Failed to review request.";
      setRowError({ id, message });
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

      <div className="card">
        <div className="table-wrap">
          <table>
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
                <tr><td colSpan={5} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>No pending face registration requests.</td></tr>
              )}
              {rows.map(r => (
                <tr key={r.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{r.employee_name}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.employee_email}</div>
                  </td>
                  <td>
                    <span className={`badge ${r.liveness_passed ? "badge-success" : "badge-error"}`}>
                      {r.liveness_passed ? "Passed" : "Failed"}
                    </span>
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{fmtScore(r.liveness_score)}</td>
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
                            onClick={() => handleReview(r.id, "rejected")}
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
    </>
  );
}
