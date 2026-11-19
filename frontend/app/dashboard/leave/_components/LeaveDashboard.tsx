"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { getLeaveYear } from "@/lib/fiscalYear";
import { useState, type CSSProperties } from "react";
import { useToast } from "@/components/ToastProvider";
import clientApi from "@/lib/clientApi";
import {
  LeaveBalance, LeaveRequest, PaginatedResponse, ReqStatus,
  STATUS_BADGE, fmtShortDate,
} from "../_data";
import LopBadge from "./LopBadge";
import LeaveRequestDetailModal from "./LeaveRequestDetailModal";
import { notifyLeaveChanged, useOnLeaveChanged } from "@/hooks/useLeaveRefresh";
import { tr } from "@/lib/i18n/tr";

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

const STATUS_TONE: Record<ReqStatus, string> = {
  pending: "lv-st-pending", l2_pending: "lv-st-pending", approved: "lv-st-approved", rejected: "lv-st-rejected", cancelled: "lv-st-cancelled",
};
const STATUS_ICON: Record<ReqStatus, string> = {
  pending: "ti-hourglass", l2_pending: "ti-hourglass", approved: "ti-circle-check", rejected: "ti-circle-x", cancelled: "ti-ban",
};

const BALANCE_DISPLAY = [
  { key: "casual" as const, get label() { return tr("Casual Leave"); }, icon: "ti-beach",      accent: "#7c3aed" },
  { key: "sick"   as const, get label() { return tr("Sick Leave"); },   icon: "ti-heartbeat",  accent: "#e11d48" },
  { key: "earned" as const, get label() { return tr("Earned Leave"); }, icon: "ti-award",      accent: "#16a34a" },
];

// Everyone — employee, manager, or HR — sees the same thing here: their own
// balances and their own leave requests. Approving other people's requests
// (manager or HR) happens exclusively in the Approvals module now.

// Four plain stat tiles — Casual/Sick/Earned available + Used This Year —
// matching the reference layout's bare label/value/sub tiles (no icon badge,
// no progress bar, no used/total line).
// Shared by the Leave tab and the Home "Leave balance" card (useFetch's
// `cache: true` means both reads of this same URL resolve from one shared
// in-memory entry instead of two separate round trips) so the two can never
// show different numbers, and the second mount never re-pays the 6-10s cold
// load the first one already paid.
export function useLeaveBalances() {
  const currentYear = getLeaveYear();
  const result = useFetch<LeaveBalance[]>(
    API.leave.balance + `?year=${currentYear}`,
    { cache: true },
  );
  // A submit / cancel / approval anywhere reloads the balance, so "Available" and "Pending" never lag behind.
  useOnLeaveChanged(result.refetch);
  return result;
}

function fmtDays(value: number | null): string {
  return value === null ? "—" : value.toFixed(1);
}

// Four plain stat tiles — Casual/Sick/Earned available + Used This Year —
// matching the reference layout's bare label/value/sub tiles (no icon badge,
// no progress bar, no used/total line).
export function LeaveBalanceStats() {
  const { data: balances, loading } = useLeaveBalances();
  const balanceMap = Object.fromEntries((balances ?? []).map(b => [b.leave_type, b]));
  // null while loading/missing — never a fabricated 0.0 (see fmtDays below).
  const usedThisYear = loading || !balances
    ? null
    : balances.reduce((sum, b) => sum + Number(b.used_days), 0);

  return (
    <div className="lv-tiles">
      {BALANCE_DISPLAY.map(({ key, label, icon, accent }) => {
        const b = balanceMap[key];
        // available_days is entitlement - used - pending (days already asked for are spoken for)
        const available = loading || !balances ? null : (b ? Number(b.available_days) : 0);
        const pending = b ? Number(b.pending_days ?? 0) : 0;
        const entitled = b ? Number(b.total_days) + Number(b.carried_forward ?? 0) : 0;
        const percentLeft = available === null || entitled <= 0 ? 0 : Math.max(0, Math.min(100, (available / entitled) * 100));
        return (
          <div key={key} className="lv-tile" style={{ "--lv-accent": accent } as CSSProperties}>
            <div className="lv-tile-top">
              <div className="lv-tile-label">{label.toUpperCase()}</div>
              <span className="lv-icon"><i className={`ti ${icon}`} /></span>
            </div>
            <div className="lv-tile-value"><b>{fmtDays(available)}</b><span>{tr("days available")}</span></div>
            <div className="lv-bar" role="img" aria-label={`${Math.round(percentLeft)} percent of ${label} left`}><i style={{ width: `${percentLeft}%` }} /></div>
            <div className="lv-tile-sub">
              <span>{entitled > 0 ? `of ${entitled.toFixed(1)} days` : tr("No entitlement")}</span>
              {pending > 0 && <span className="lv-pending">{pending.toFixed(1)} {tr("pending")}</span>}
            </div>
          </div>
        );
      })}

      {/* Used This Year — total leave days already used (deducted) across every
          leave type this calendar year, summed from the same real balance
          rows the accrued cards above read from (not a separate fabricated
          count). */}
      <div className="lv-tile" style={{ "--lv-accent": "#0ea5e9" } as CSSProperties}>
        <div className="lv-tile-top">
          <div className="lv-tile-label">{tr("USED THIS YEAR")}</div>
          <span className="lv-icon"><i className="ti ti-calendar-check" /></span>
        </div>
        <div className="lv-tile-value"><b>{fmtDays(usedThisYear)}</b><span>{tr("days approved")}</span></div>
        <div className="lv-tile-sub"><span>{tr("Across all leave types")}</span></div>
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

  useOnLeaveChanged(refetchRequests);

  const requestList = requests?.results ?? [];
  const recentRequests = requestList.slice(0, RECENT_COUNT);

  async function cancelMine(id: string) {
    try {
      const res = await clientApi.patch<{ message: string }>(API.leave.requestDetail(id));
      showToast(res.data.message, "success");
      refetchRequests();
      notifyLeaveChanged();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to cancel leave request.", "error");
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title"><i className="ti ti-list-details" /> {tr("My leave requests")}</div>
          <div className="page-sub" style={{ marginTop: 2 }}>{tr("Approval status and history.")}</div>
        </div>
      </div>
      <div className="card-body" style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: "40px 20px", textAlign: "center" }}>
            <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
          </div>
        ) : recentRequests.length === 0 ? (
          <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
            {tr("No leave requests yet.")}
          </div>
        ) : (
          recentRequests.map(r => {
            const dateLabel = r.start_date === r.end_date
              ? fmtShortDate(r.start_date)
              : `${fmtShortDate(r.start_date)} - ${fmtShortDate(r.end_date)}`;
            const approver = r.l2_approver_name || r.l1_approver_name || r.approved_by || null;
            return (
              <div key={r.id} className={`lv-row is-click ${STATUS_TONE[r.status]}`} onClick={() => setDetailRequest(r)}>
                <span className="lv-glyph"><i className={`ti ${STATUS_ICON[r.status]}`} /></span>
                <div className="lv-row-main">
                  <div className="lv-row-title">{r.leave_type_display} · {dateLabel}</div>
                  <div className="lv-row-meta">
                    {tr(r.total_days === 1 ? "{count} day" : "{count} days", { count: r.total_days })} · {r.reason || approver || "—"}
                    <LopBadge request={r} />
                  </div>
                </div>
                <span className={STATUS_BADGE[r.status]}>{SHORT_STATUS_LABEL[r.status]}</span>
                <i className="ti ti-chevron-right lv-chevron" />
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
