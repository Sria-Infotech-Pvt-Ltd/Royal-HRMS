"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { getLeaveYear } from "@/lib/fiscalYear";
import { useState } from "react";
import { useToast } from "@/components/ToastProvider";
import clientApi from "@/lib/clientApi";
import {
  LeaveBalance, LeaveRequest, LeaveStats, PaginatedResponse,
  fmtShortDate,
} from "../_data";
import StatusCell from "./StatusCell";
import LopBadge from "./LopBadge";
import LeaveRequestDetailModal from "./LeaveRequestDetailModal";

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
  const { data: stats } = useFetch<LeaveStats>(
    API.leave.stats + `?year=${currentYear}&scope=own`
  );

  const balanceMap = Object.fromEntries((balances ?? []).map(b => [b.leave_type, b]));
  const requestList = requests?.results ?? [];
  const recentRequests = requestList.slice(0, RECENT_COUNT);
  const lopBalance = balanceMap["lwp"];

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
                  <div className="stat-sub">Available</div>
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

        {/* Loss of Pay — shown the same shape as the accrued balances; most
            policies don't cap LWP, so fall back to the running LOP-days-taken
            count when the balance endpoint has no fixed total for it. */}
        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Loss of Pay (LOP)</div>
              <div className="stat-value" style={{ color: "var(--warn)" }}>
                {lopBalance ? Number(lopBalance.total_days) - Number(lopBalance.used_days) : "—"}
              </div>
              <div className="stat-sub">Available</div>
            </div>
            <div className="stat-icon si-warn" style={{ float: "none", margin: 0 }}>
              <i className="ti ti-coin-off" />
            </div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: lopBalance && Number(lopBalance.total_days) > 0 ? `${Math.round((Number(lopBalance.used_days) / Number(lopBalance.total_days)) * 100)}%` : "0%", background: "var(--warn)" }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: "var(--on-variant)" }}>
            <span>Used: {lopBalance ? Number(lopBalance.used_days) : (stats?.lop_days ?? 0)}</span>
            <span>Total: {lopBalance ? Number(lopBalance.total_days) : "No cap"}</span>
          </div>
        </div>
      </div>

      {/* Recent Leave Requests — latest 5 only; full history lives in My Requests */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <i className="ti ti-list-details" /> Recent Leave Requests
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
        <div className="table-wrap">
          {loading ? (
            <div style={{ padding: "40px 20px", textAlign: "center" }}>
              <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
            </div>
          ) : recentRequests.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
              No leave requests yet. Click <strong>Apply Leave</strong> to get started.
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Leave Type</th>
                  <th>From Date</th>
                  <th>To Date</th>
                  <th style={{ textAlign: "center" }}>Days</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {recentRequests.map(r => (
                  <tr key={r.id} onClick={() => setDetailRequest(r)} style={{ cursor: "pointer" }}>
                    <td>{r.leave_type_display}</td>
                    <td>{fmtShortDate(r.start_date)}</td>
                    <td>{fmtShortDate(r.end_date)}</td>
                    <td style={{ textAlign: "center", fontWeight: 700 }}>
                      {r.total_days}
                      <LopBadge request={r} />
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <StatusCell request={r} />
                    </td>
                    <td style={{ textAlign: "right" }} onClick={e => e.stopPropagation()}>
                      <button className="btn btn-ghost btn-sm" onClick={() => setDetailRequest(r)} suppressHydrationWarning>
                        <i className="ti ti-eye" /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
