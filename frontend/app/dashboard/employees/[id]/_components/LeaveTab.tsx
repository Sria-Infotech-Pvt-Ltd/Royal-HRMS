"use client";

import { useState } from "react";
import { useEmployeeLeave } from "@/hooks/useEmployeeLeave";
import {
  LEAVE_TYPE_CONFIG, STATUS_BADGE, STATUS_LABEL, fmtShortDate,
  type LeaveRequest, type LeaveTypeKey,
} from "@/app/dashboard/leave/_data";
import LeaveRequestDetailModal from "@/app/dashboard/leave/_components/LeaveRequestDetailModal";
import LopBadge from "@/app/dashboard/leave/_components/LopBadge";

interface Props {
  employeeId: string;
}

const BALANCE_DISPLAY: { key: LeaveTypeKey; icon: string; iconClass: string; barColor: string }[] = [
  { key: "casual", icon: "ti-circle-check", iconClass: "si-success", barColor: "var(--success)" },
  { key: "earned", icon: "ti-calendar",     iconClass: "si-primary", barColor: "var(--primary)" },
  { key: "sick",   icon: "ti-stethoscope",  iconClass: "si-info",    barColor: "var(--info)"    },
];

export function LeaveTab({ employeeId }: Props) {
  const [detailRequest, setDetailRequest] = useState<LeaveRequest | null>(null);
  const { year, prevYear, nextYear, page, setPage, totalPages, requests, stats, loading, error } =
    useEmployeeLeave(employeeId);

  const balanceMap = Object.fromEntries((stats?.balances ?? []).map(b => [b.leave_type, b]));

  if (error) {
    return (
      <div className="alert alert-error">
        <i className="ti ti-alert-circle" /> {error}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="stats-grid" style={{ marginBottom: 0 }}>
        {BALANCE_DISPLAY.map(({ key, icon, iconClass, barColor }) => {
          const b     = balanceMap[key];
          const total = b ? Number(b.total_days) : 0;
          const left  = b ? Number(b.available)  : 0;
          const used  = b ? Number(b.used_days)  : 0;
          const pct   = total > 0 ? Math.round((used / total) * 100) : 0;
          return (
            <div key={key} className="stat-card">
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
                <div>
                  <div className="stat-label">{LEAVE_TYPE_CONFIG[key].label}</div>
                  <div className="stat-value">{loading ? "—" : left}</div>
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
              <div className="stat-label">Pending Requests</div>
              <div className="stat-value">{loading ? "—" : stats?.pending ?? 0}</div>
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
              <div className="stat-value" style={{ color: "var(--warn)" }}>{loading ? "—" : stats?.lop_days ?? 0}</div>
              <div className="stat-sub">
                {loading ? "" : `${stats?.lop_requests ?? 0} request${(stats?.lop_requests ?? 0) !== 1 ? "s" : ""} in ${year}`}
              </div>
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
            <i className="ti ti-list-details" /> Leave Requests
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button className="btn btn-ghost btn-sm" onClick={prevYear} disabled={loading}>
              <i className="ti ti-chevron-left" />
            </button>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", minWidth: 48, textAlign: "center" }}>
              {year}
            </span>
            <button className="btn btn-ghost btn-sm" onClick={nextYear} disabled={loading}>
              <i className="ti ti-chevron-right" />
            </button>
          </div>
        </div>
        <div className="table-wrap">
          {loading ? (
            <div style={{ padding: "40px 20px", textAlign: "center" }}>
              <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
            </div>
          ) : requests.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
              No leave requests found for {year}.
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
                {requests.map(r => (
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
                      <span className={STATUS_BADGE[r.status]}>{STATUS_LABEL[r.status]}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {totalPages > 1 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
              <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {page} of {totalPages}</span>
              <div style={{ display: "flex", gap: 6 }}>
                <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                  <i className="ti ti-chevron-left" /> Prev
                </button>
                <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(p + 1, totalPages))}>
                  Next <i className="ti ti-chevron-right" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {detailRequest && (
        <LeaveRequestDetailModal
          requestId={detailRequest.id}
          initialData={detailRequest}
          onClose={() => setDetailRequest(null)}
        />
      )}
    </div>
  );
}
