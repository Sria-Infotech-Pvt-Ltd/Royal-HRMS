"use client";

// "Feedback requests" — the employee's own feedback_request-topic
// HRHelpRequest rows (see GrowthFeedbackRequestModal.tsx for why this reuses
// the generic HR Help model instead of a dedicated one). The list endpoint
// already scopes a plain employee to their own requests server-side
// (HRHelpRequestListCreateView.get) — filtered here to this one topic.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import type { PaginatedResponse } from "@/types/attendance";

interface HrHelpRequest {
  id: string;
  topic: string;
  message: string;
  status: string;
  status_display: string;
  created_at: string;
}

const STATUS_BADGE: Record<string, string> = {
  open: "badge-warn", in_progress: "badge-info", resolved: "badge-success",
};

export default function GrowthFeedbackRequestsCard() {
  const { data, loading } = useFetch<PaginatedResponse<HrHelpRequest>>(`${API.hrHelp.list}?page_size=50`);
  const requests = (data?.results ?? []).filter(r => r.topic === "feedback_request");

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-message-heart" /> Feedback requests</div>
      </div>
      {loading ? (
        <div style={{ padding: "4px 20px 20px" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--on-variant)" }} />
        </div>
      ) : requests.length === 0 ? (
        <div style={{ padding: "4px 20px 20px" }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>No feedback requests</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>
            Ask a manager or colleague for focused feedback.
          </div>
        </div>
      ) : (
        <div style={{ padding: "4px 0 8px" }}>
          {requests.map((r, idx) => (
            <div
              key={r.id}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "12px 20px", gap: 12,
                borderTop: idx === 0 ? "none" : "1px solid var(--outline-v)",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{r.message}</div>
                <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                  Requested {formatDate(r.created_at)}
                </div>
              </div>
              <span className={`badge ${STATUS_BADGE[r.status] ?? "badge-neutral"}`}>{r.status_display}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
