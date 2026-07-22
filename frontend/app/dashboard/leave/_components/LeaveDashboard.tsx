"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import {
  LeaveBalance, LeaveRequest, LeaveStats, PaginatedResponse,
  LEAVE_TYPE_CONFIG,
  fmtShortDate,
} from "../_data";
import RejectModal from "./RejectModal";
import StatusCell from "./StatusCell";
import LopBadge from "./LopBadge";
import LeaveRequestDetailModal from "./LeaveRequestDetailModal";

interface Props {
  role:    string;
  onApply: () => void;
  branch:  string;
}

const BALANCE_DISPLAY = [
  { key: "casual" as const, icon: "ti-circle-check", iconClass: "si-success", barColor: "var(--success)" },
  { key: "earned" as const, icon: "ti-calendar",     iconClass: "si-primary",  barColor: "var(--primary)" },
  { key: "sick"   as const, icon: "ti-stethoscope",  iconClass: "si-info",     barColor: "var(--info)"    },
];

export default function LeaveDashboard({ role, onApply, branch }: Props) {
  const { showToast } = useToast();
  const isEmployee = role === "employee";

  const [rejectTarget, setRejectTarget] = useState<{ id: string; employee: string; type: string } | null>(null);
  const [detailRequest, setDetailRequest] = useState<LeaveRequest | null>(null);
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState<"pending" | "mine">("pending");

  // Branch filter changed — the current page no longer means the same thing.
  useEffect(() => { setPage(1); }, [branch]);

  const currentYear = new Date().getFullYear();

  const { data: balances } = useFetch<LeaveBalance[]>(
    API.leave.balance + `?year=${currentYear}`
  );

  // Employee: all their own requests, no scope/status/branch/page — this list
  // is never paginated in the UI today and is always small (one person's own
  // requests). Approver: the queue — one URL for every approver role; backend
  // returns pending for managers and l2_pending for HR automatically. Never
  // hardcode a status filter here. branch/page are system_admin-only (branch
  // is always "" for manager/hr_admin, who are already branch-scoped server-side).
  const requestsUrl = isEmployee
    ? API.leave.requests
    : API.leave.requests
      + "?scope=team"
      + (branch ? `&branch=${encodeURIComponent(branch)}` : "")
      + `&page=${page}`;

  const { data: requests, refetch: refetchRequests, loading } = useFetch<PaginatedResponse<LeaveRequest>>(requestsUrl);

  // Approver's own leave requests — a separate "My Leave Requests" tab. Never
  // mixed into requestsUrl above: scope=team explicitly excludes the approver's
  // own rows, so this is always the bare endpoint (no scope param = own requests).
  const { data: myRequests, refetch: refetchMine, loading: loadingMine } = useFetch<PaginatedResponse<LeaveRequest>>(
    isEmployee ? null : API.leave.requests
  );
  const myRequestList = myRequests?.results ?? [];

  const statsUrl = isEmployee
    ? API.leave.stats + `?year=${currentYear}&scope=own`
    : API.leave.stats + `?year=${currentYear}&scope=team`;

  const { data: stats, refetch: refetchStats } = useFetch<LeaveStats>(statsUrl);

  const balanceMap = Object.fromEntries((balances ?? []).map(b => [b.leave_type, b]));

  const requestList = requests?.results ?? [];

  async function approve(id: string) {
    try {
      await clientApi.post(API.leave.approve(id), { action: "approve" });
      refetchRequests();
      refetchStats();
    } catch {
      // silently handled
    }
  }

  async function handleReject(reason: string) {
    if (!rejectTarget) return;
    try {
      await clientApi.post(API.leave.approve(rejectTarget.id), { action: "reject", remarks: reason });
      refetchRequests();
      refetchStats();
    } catch {
      // silently handled
    } finally {
      setRejectTarget(null);
    }
  }

  async function cancelMine(id: string) {
    try {
      const res = await clientApi.patch<{ message: string }>(API.leave.requestDetail(id));
      showToast(res.data.message, "success");
      refetchRequests();
      refetchMine();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to cancel leave request.", "error");
    }
  }

  // ── Employee layout ────────────────────────────────────────────────────────
  if (isEmployee) {
    const ownPending = requestList.filter(
      r => r.status === "pending" || r.status === "l2_pending"
    ).length;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

        <div className="stats-grid" style={{ marginBottom: 0 }}>
          {BALANCE_DISPLAY.map(({ key, icon, iconClass, barColor }) => {
            const b     = balanceMap[key];
            const total = b ? Number(b.total_days) : 0;
            const used  = b ? Number(b.used_days)  : 0;
            const left  = total - used;
            const pct   = total > 0 ? Math.round((used / total) * 100) : 0;
            return (
              <div key={key} className="stat-card">
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
                  <div>
                    <div className="stat-label">{LEAVE_TYPE_CONFIG[key].label}</div>
                    <div className="stat-value">{left}</div>
                    <div className="stat-sub">of {total} days left</div>
                  </div>
                  <div className={`stat-icon ${iconClass}`} style={{ float: "none", margin: 0 }}>
                    <i className={`ti ${icon}`} />
                  </div>
                </div>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${pct}%`, background: barColor }} />
                </div>
              </div>
            );
          })}

          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
              <div>
                <div className="stat-label">My Pending</div>
                <div className="stat-value">{ownPending}</div>
                <div className="stat-sub">Awaiting approval</div>
              </div>
              <div className="stat-icon si-warn" style={{ float: "none", margin: 0 }}>
                <i className="ti ti-clock" />
              </div>
            </div>
            <div className="progress-bar"><div className="progress-fill" style={{ width: 0 }} /></div>
          </div>

          <div className="stat-card">
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
              <div>
                <div className="stat-label">Loss of Pay (LOP)</div>
                <div className="stat-value" style={{ color: "var(--warn)" }}>{stats?.lop_days ?? 0}</div>
                <div className="stat-sub">{stats?.lop_requests ?? 0} request{(stats?.lop_requests ?? 0) !== 1 ? "s" : ""} in {currentYear}</div>
              </div>
              <div className="stat-icon si-warn" style={{ float: "none", margin: 0 }}>
                <i className="ti ti-coin-off" />
              </div>
            </div>
            <div className="progress-bar"><div className="progress-fill" style={{ width: 0 }} /></div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <i className="ti ti-list-details" /> My Leave Requests
            </div>
            <button className="btn btn-filled btn-sm" onClick={onApply}>
              <i className="ti ti-plus" /> Apply Leave
            </button>
          </div>
          <div className="table-wrap">
            {loading ? (
              <div style={{ padding: "40px 20px", textAlign: "center" }}>
                <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
              </div>
            ) : requestList.length === 0 ? (
              <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                No leave requests yet. Click <strong>Apply Leave</strong> to get started.
              </div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Leave Type</th>
                    <th>From</th>
                    <th>To</th>
                    <th style={{ textAlign: "center" }}>Days</th>
                    <th>Applied On</th>
                    <th>Approver</th>
                    <th style={{ textAlign: "center" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {requestList.map(r => (
                    <tr key={r.id} onClick={() => setDetailRequest(r)} style={{ cursor: "pointer" }}>
                      <td>{r.leave_type_display}</td>
                      <td>{fmtShortDate(r.start_date)}</td>
                      <td>{fmtShortDate(r.end_date)}</td>
                      <td style={{ textAlign: "center", fontWeight: 700 }}>
                        {r.total_days}
                        <LopBadge request={r} />
                      </td>
                      <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{fmtShortDate(r.created_at?.slice(0, 10))}</td>
                      <td style={{ fontSize: 13, color: "var(--on-variant)" }}>
                        {r.approved_by || "—"}
                        {r.approved_at
                          ? <div style={{ fontSize: 11, color: "var(--outline)" }}>{fmtShortDate(r.approved_at.slice(0, 10))}</div>
                          : <div style={{ fontSize: 11, color: "var(--outline)" }}>Not yet actioned</div>}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <StatusCell request={r} />
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

  // ── Approver layout (manager / hr / system_admin) ─────────────────────────
  const pendingCount = stats?.pending ?? 0;
  const scopeLabel   = role === "manager__team_lead" ? "Your team's requests"
                     : role === "hr"                 ? "Your branch requests"
                     : "Organisation-wide requests";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      <div className="stats-grid" style={{ marginBottom: 0 }}>
        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Pending Approvals</div>
              <div className="stat-value">{pendingCount}</div>
              <div className="stat-sub">{scopeLabel}</div>
            </div>
            <div className="stat-icon si-warn" style={{ float: "none", margin: 0 }}>
              <i className="ti ti-checks" />
            </div>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: 0 }} /></div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Loss of Pay (LOP)</div>
              <div className="stat-value" style={{ color: "var(--warn)" }}>{stats?.lop_days ?? 0}</div>
              <div className="stat-sub">{stats?.lop_requests ?? 0} request{(stats?.lop_requests ?? 0) !== 1 ? "s" : ""} · {scopeLabel}</div>
            </div>
            <div className="stat-icon si-warn" style={{ float: "none", margin: 0 }}>
              <i className="ti ti-coin-off" />
            </div>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: 0 }} /></div>
        </div>

        {BALANCE_DISPLAY.map(({ key, icon, iconClass, barColor }) => {
          const b     = balanceMap[key];
          const total = b ? Number(b.total_days) : 0;
          const used  = b ? Number(b.used_days)  : 0;
          const left  = total - used;
          const pct   = total > 0 ? Math.round((used / total) * 100) : 0;
          return (
            <div key={key} className="stat-card">
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
                <div>
                  <div className="stat-label">My {LEAVE_TYPE_CONFIG[key].shortLabel}</div>
                  <div className="stat-value">{left}</div>
                  <div className="stat-sub">of {total} days left</div>
                </div>
                <div className={`stat-icon ${iconClass}`} style={{ float: "none", margin: 0 }}>
                  <i className={`ti ${icon}`} />
                </div>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${pct}%`, background: barColor }} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="card">
        <div className="card-header" style={{ flexWrap: "wrap", gap: 10 }}>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              className={`btn btn-sm ${tab === "pending" ? "btn-filled" : "btn-ghost"}`}
              onClick={() => setTab("pending")}
            >
              <i className="ti ti-list-details" /> Pending Approvals
              {requests && requests.count > 0 && (
                <span style={{ fontSize: 12, fontWeight: 400, marginLeft: 4 }}>· {requests.count}</span>
              )}
            </button>
            <button
              className={`btn btn-sm ${tab === "mine" ? "btn-filled" : "btn-ghost"}`}
              onClick={() => setTab("mine")}
            >
              <i className="ti ti-user" /> My Leave Requests
            </button>
          </div>
          <button className="btn btn-filled btn-sm" onClick={onApply}>
            <i className="ti ti-plus" /> Apply My Leave
          </button>
        </div>

        <div className="table-wrap">
          {(tab === "pending" ? loading : loadingMine) ? (
            <div style={{ padding: "40px 20px", textAlign: "center" }}>
              <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
            </div>
          ) : tab === "pending" ? (
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Branch</th>
                  <th>Leave Type</th>
                  <th>From</th>
                  <th>To</th>
                  <th style={{ textAlign: "center" }}>Days</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {requestList.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", padding: "40px 20px" }}>
                      <i className="ti ti-building" style={{ fontSize: 28, display: "block", marginBottom: 8, color: "var(--outline-v)" }} />
                      <span style={{ color: "var(--on-variant)", fontSize: 13 }}>
                        {branch ? "No requests for the selected branch." : "No pending leave requests."}
                      </span>
                    </td>
                  </tr>
                ) : requestList.map(r => (
                  <tr key={r.id} onClick={() => setDetailRequest(r)} style={{ cursor: "pointer" }}>
                    <td style={{ fontWeight: 600 }}>{r.employee_name}</td>
                    <td><span className="badge badge-neutral">{r.employee_branch || "—"}</span></td>
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
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Leave Type</th>
                  <th>From</th>
                  <th>To</th>
                  <th style={{ textAlign: "center" }}>Days</th>
                  <th>Applied On</th>
                  <th>Approver</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {myRequestList.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", padding: "40px 20px" }}>
                      <span style={{ color: "var(--on-variant)", fontSize: 13 }}>
                        You have not applied for any leave yet.
                      </span>
                    </td>
                  </tr>
                ) : myRequestList.map(r => (
                  <tr key={r.id} onClick={() => setDetailRequest(r)} style={{ cursor: "pointer" }}>
                    <td>{r.leave_type_display}</td>
                    <td>{fmtShortDate(r.start_date)}</td>
                    <td>{fmtShortDate(r.end_date)}</td>
                    <td style={{ textAlign: "center", fontWeight: 700 }}>
                      {r.total_days}
                      <LopBadge request={r} />
                    </td>
                    <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{fmtShortDate(r.created_at?.slice(0, 10))}</td>
                    <td style={{ fontSize: 13, color: "var(--on-variant)" }}>
                      {r.approved_by || "—"}
                      {r.approved_at
                        ? <div style={{ fontSize: 11, color: "var(--outline)" }}>{fmtShortDate(r.approved_at.slice(0, 10))}</div>
                        : <div style={{ fontSize: 11, color: "var(--outline)" }}>Not yet actioned</div>}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <StatusCell request={r} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {tab === "pending" && requests && requests.total_pages > 1 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
              <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {requests.page} of {requests.total_pages}</span>
              <div style={{ display: "flex", gap: 6 }}>
                <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                  <i className="ti ti-chevron-left" /> Prev
                </button>
                <button className="btn btn-ghost btn-sm" disabled={page >= requests.total_pages} onClick={() => setPage(p => Math.min(p + 1, requests.total_pages))}>
                  Next <i className="ti ti-chevron-right" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {rejectTarget && (
        <RejectModal
          employee={rejectTarget.employee}
          leaveType={rejectTarget.type}
          onCancel={() => setRejectTarget(null)}
          onConfirm={handleReject}
        />
      )}

      {detailRequest && (
        <LeaveRequestDetailModal
          requestId={detailRequest.id}
          initialData={detailRequest}
          onClose={() => setDetailRequest(null)}
          onApprove={tab === "pending" ? () => approve(detailRequest.id) : undefined}
          onReject={tab === "pending" ? () => setRejectTarget({ id: detailRequest.id, employee: detailRequest.employee_name, type: detailRequest.leave_type_display }) : undefined}
          onCancelRequest={tab === "mine" ? () => cancelMine(detailRequest.id) : undefined}
        />
      )}
    </div>
  );
}
