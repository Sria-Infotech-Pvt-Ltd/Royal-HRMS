"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { getLeaveYear } from "@/lib/fiscalYear";
import { useState } from "react";
import { useToast } from "@/components/ToastProvider";
import clientApi from "@/lib/clientApi";
import {
  LeaveBalance, LeaveRequest, PaginatedResponse, ReqStatus,
  STATUS_BADGE, fmtShortDate,
} from "../_data";
import LopBadge from "./LopBadge";
import LeaveRequestDetailModal from "./LeaveRequestDetailModal";

// Short pill text for this card only — "PENDING"/"APPROVED" rather than
// StatusCell's longer "Pending Manager Approval" wording used elsewhere.
const SHORT_STATUS_LABEL: Record<ReqStatus, string> = {
  pending:    "PENDING",
  l2_pending: "PENDING",
  approved:   "APPROVED",
  rejected:   "REJECTED",
  cancelled:  "CANCELLED",
};

const RECENT_COUNT = 5;

const BALANCE_DISPLAY = [
  { key: "casual" as const, label: "Casual Leave" },
  { key: "sick"   as const, label: "Sick Leave"   },
  { key: "earned" as const, label: "Earned Leave" },
];

// Everyone — employee, manager, or HR — sees the same thing here: their own
// balances and their own leave requests. Approving other people's requests
// (manager or HR) happens exclusively in the Approvals module now.

// Four plain stat tiles — Casual/Sick/Earned available + Used This Year —
// matching the reference layout's bare label/value/sub tiles (no icon badge,
// no progress bar, no used/total line).
export function LeaveBalanceStats() {
  const currentYear = getLeaveYear();
  const { data: balances } = useFetch<LeaveBalance[]>(
    API.leave.balance + `?year=${currentYear}`
  );
  const balanceMap = Object.fromEntries((balances ?? []).map(b => [b.leave_type, b]));
  const usedThisYear = (balances ?? []).reduce((sum, b) => sum + Number(b.used_days), 0);

  return (
    <div className="stats-grid" style={{ marginBottom: 0 }}>
      {BALANCE_DISPLAY.map(({ key, label }) => {
        const b         = balanceMap[key];
        const total     = b ? Number(b.total_days) : 0;
        const used      = b ? Number(b.used_days)  : 0;
        const available = total - used;
        return (
          <div key={key} className="stat-card">
            <div className="stat-label">{label.toUpperCase()}</div>
            <div className="stat-value">{available.toFixed(1)}</div>
            <div className="stat-sub">days available</div>
          </div>
        );
      })}

      {/* Used This Year — total leave days already used (deducted) across every
          leave type this calendar year, summed from the same real balance
          rows the accrued cards above read from (not a separate fabricated
          count). */}
      <div className="stat-card">
        <div className="stat-label">USED THIS YEAR</div>
        <div className="stat-value">{usedThisYear.toFixed(1)}</div>
        <div className="stat-sub">days approved</div>
      </div>
    </div>
  );
}

// "My leave requests" — latest 5 only; full history lives in My Requests.
// No header action buttons — matches the reference card, which shows only
// the title/subtitle (the page-level "Request leave" button already covers
// applying, and the Leave Calendar/Analytics modals stay reachable via their
// own deep-link query params even with no visible trigger here).
export default function LeaveDashboard() {
  const { showToast } = useToast();
  const [detailRequest, setDetailRequest] = useState<LeaveRequest | null>(null);

  const { data: requests, refetch: refetchRequests, loading } = useFetch<PaginatedResponse<LeaveRequest>>(
    API.leave.requests
  );

  const requestList = requests?.results ?? [];
  const recentRequests = requestList.slice(0, RECENT_COUNT);

  async function cancelMine(id: string) {
    try {
      const res = await clientApi.patch<{ message: string }>(API.leave.requestDetail(id));
      showToast(res.data.message, "success");
      refetchRequests();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to cancel leave request.", "error");
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title"><i className="ti ti-list-details" /> My leave requests</div>
          <div className="page-sub" style={{ marginTop: 2 }}>Approval status and history.</div>
        </div>
      </div>
      <div className="card-body" style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: "40px 20px", textAlign: "center" }}>
            <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
          </div>
        ) : recentRequests.length === 0 ? (
          <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
            No leave requests yet.
          </div>
        ) : (
          recentRequests.map((r, idx) => {
            const dateLabel = r.start_date === r.end_date
              ? fmtShortDate(r.start_date)
              : `${fmtShortDate(r.start_date)} - ${fmtShortDate(r.end_date)}`;
            const approver = r.l2_approver_name || r.l1_approver_name || r.approved_by || null;
            return (
              <div
                key={r.id}
                onClick={() => setDetailRequest(r)}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "12px 20px", cursor: "pointer",
                  borderTop: idx === 0 ? "none" : "1px solid var(--outline-v)",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
                    {r.leave_type_display} · {dateLabel}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                    {r.total_days} day{r.total_days === 1 ? "" : "s"} · {r.reason || approver || "—"}
                    <LopBadge request={r} />
                  </div>
                </div>
                <span className={STATUS_BADGE[r.status]}>{SHORT_STATUS_LABEL[r.status]}</span>
              </div>
            );
          })
        )}
      </div>

      {detailRequest && (
        <LeaveRequestDetailModal
          requestId={detailRequest.id}
          initialData={detailRequest}
          onClose={() => setDetailRequest(null)}
          onCancelRequest={() => cancelMine(detailRequest.id)}
        />
      )}
    </div>
  );
}
