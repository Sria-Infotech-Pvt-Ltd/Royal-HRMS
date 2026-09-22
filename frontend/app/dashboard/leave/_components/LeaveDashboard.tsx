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

interface Props {
  onApply:        () => void;
  onViewCalendar: () => void;
}

const RECENT_COUNT = 5;

const BALANCE_DISPLAY = [
  { key: "casual" as const, label: "Casual Leave", icon: "ti-circle-check", iconClass: "si-success", barColor: "var(--success)" },
  { key: "sick"   as const, label: "Sick Leave",   icon: "ti-stethoscope",  iconClass: "si-info",     barColor: "var(--info)"    },
  { key: "earned" as const, label: "Earned Leave", icon: "ti-calendar",     iconClass: "si-primary",  barColor: "var(--primary)" },
];

// Everyone — employee, manager, or HR — sees the same thing here: their own
// balances and their own leave requests. Approving other people's requests
// (manager or HR) happens exclusively in the Approvals module now.
export default function LeaveDashboard({ onApply, onViewCalendar }: Props) {
  const { showToast } = useToast();
  const [detailRequest, setDetailRequest] = useState<LeaveRequest | null>(null);

  const currentYear = getLeaveYear();

  const { data: balances } = useFetch<LeaveBalance[]>(
    API.leave.balance + `?year=${currentYear}`
  );
  const { data: requests, refetch: refetchRequests, loading } = useFetch<PaginatedResponse<LeaveRequest>>(
    API.leave.requests
  );

  const balanceMap = Object.fromEntries((balances ?? []).map(b => [b.leave_type, b]));
  const requestList = requests?.results ?? [];
  const recentRequests = requestList.slice(0, RECENT_COUNT);
  // Total days already used (deducted) across every leave type this year —
  // the same balance rows the accrued cards above read from.
  const usedThisYear = (balances ?? []).reduce((sum, b) => sum + Number(b.used_days), 0);

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
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Leave Balance Cards — Available / Used / Total */}
      <div className="stats-grid" style={{ marginBottom: 0 }}>
        {BALANCE_DISPLAY.map(({ key, label, icon, iconClass, barColor }) => {
          const b         = balanceMap[key];
          const total     = b ? Number(b.total_days) : 0;
          const used      = b ? Number(b.used_days)  : 0;
          const available = total - used;
          const pct       = total > 0 ? Math.round((used / total) * 100) : 0;
          return (
            <div key={key} className="stat-card">
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
                <div>
                  <div className="stat-label">{label}</div>
                  <div className="stat-value">{available}</div>
                  <div className="stat-sub">days available</div>
                </div>
                <div className={`stat-icon ${iconClass}`} style={{ float: "none", margin: 0 }}>
                  <i className={`ti ${icon}`} />
                </div>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${pct}%`, background: barColor }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: "var(--on-variant)" }}>
                <span>Used: {used}</span>
                <span>Total: {total}</span>
              </div>
            </div>
          );
        })}

        {/* Used This Year — total leave days already used (deducted) across every
            leave type this calendar year, summed from the same real balance
            rows the accrued cards above read from (not a separate fabricated
            count). */}
        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Used This Year</div>
              <div className="stat-value">{usedThisYear}</div>
              <div className="stat-sub">days approved</div>
            </div>
            <div className="stat-icon si-warn" style={{ float: "none", margin: 0 }}>
              <i className="ti ti-calendar-stats" />
            </div>
          </div>
        </div>
      </div>

      {/* My leave requests — latest 5 only; full history lives in My Requests */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title"><i className="ti ti-list-details" /> My leave requests</div>
            <div className="page-sub" style={{ marginTop: 2 }}>Approval status and history.</div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={onViewCalendar} suppressHydrationWarning>
              <i className="ti ti-calendar" /> Leave Calendar
            </button>
            <button className="btn btn-filled btn-sm" onClick={onApply} suppressHydrationWarning>
              <i className="ti ti-plus" /> Apply Leave
            </button>
            <a href="/dashboard/my-requests?tab=leave" className="btn btn-ghost btn-sm">
              View All <i className="ti ti-arrow-right" />
            </a>
          </div>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {loading ? (
            <div style={{ padding: "40px 20px", textAlign: "center" }}>
              <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
            </div>
          ) : recentRequests.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
              No leave requests yet. Click <strong>Apply Leave</strong> to get started.
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
