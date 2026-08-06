"use client";

import { useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import RegularizationModal from "./RegularizationModal";
import MyCorrectionDetailModal from "../../my-requests/_components/MyCorrectionDetailModal";
import {
  MyCorrectionRequest, PaginatedResponse, STATUS_BADGE_CLASS, STATUS_LABEL,
  fmtSubmitted, fmtTime12h, toDisplayStatus,
} from "../../my-requests/_data";

const RECENT_COUNT = 5;

export default function AttendanceCorrectionsTab({ autoOpenNew = false }: { autoOpenNew?: boolean }) {
  const [showNew, setShowNew] = useState(autoOpenNew);
  const [detail, setDetail]   = useState<MyCorrectionRequest | null>(null);

  const { data, loading, error, refetch } = useFetch<PaginatedResponse<MyCorrectionRequest>>(
    `${API.attendance.myCorrections}?page_size=100`
  );

  const corrections = useMemo(() => [...(data?.results ?? [])].sort(
    (a, b) => new Date(b.created_at.replace(" ", "T")).getTime() - new Date(a.created_at.replace(" ", "T")).getTime()
  ), [data]);

  const counts = useMemo(() => {
    let pending = 0, approved = 0, rejected = 0;
    for (const c of corrections) {
      const s = toDisplayStatus(c.status);
      if (s === "pending") pending++;
      else if (s === "approved") approved++;
      else if (s === "rejected") rejected++;
    }
    return { pending, approved, rejected };
  }, [corrections]);

  const recent = corrections.slice(0, RECENT_COUNT);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Summary cards */}
      <div className="stats-grid" style={{ marginBottom: 0 }}>
        <div className="stat-card">
          <div className="stat-icon si-warn"><i className="ti ti-clock" /></div>
          <div className="stat-label">Pending</div>
          <div className="stat-value">{loading ? "—" : counts.pending}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-success"><i className="ti ti-check" /></div>
          <div className="stat-label">Approved</div>
          <div className="stat-value">{loading ? "—" : counts.approved}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-error"><i className="ti ti-x" /></div>
          <div className="stat-label">Rejected</div>
          <div className="stat-value">{loading ? "—" : counts.rejected}</div>
        </div>
      </div>

      {/* Quick Action */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-bolt" /> Quick Actions</div>
        </div>
        <div className="card-body">
          <div className="qa-grid">
            <button className="qa-tile" onClick={() => setShowNew(true)} suppressHydrationWarning>
              <div className="qa-icon si-warn"><i className="ti ti-file-description" /></div>
              <span className="qa-label">Request Attendance Correction</span>
            </button>
          </div>
        </div>
      </div>

      {error && <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error}</div>}

      {/* Recent corrections — latest 5; full history lives in My Requests */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-clock-edit" /> Recent Correction Requests</div>
          <a href="/dashboard/my-requests?tab=attendance_correction" className="btn btn-ghost btn-sm">
            View All Corrections <i className="ti ti-arrow-right" />
          </a>
        </div>
        <div className="table-wrap">
          {loading ? (
            <div style={{ padding: "40px 20px", textAlign: "center" }}>
              <i className="ti ti-loader-2 spin" style={{ fontSize: 24, color: "var(--primary)" }} />
            </div>
          ) : recent.length === 0 ? (
            <div className="empty-state">
              <i className="ti ti-clock-edit" />
              <h3>No correction requests yet</h3>
              <p>Use Request Attendance Correction above if a punch was missed or recorded incorrectly.</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Check-In</th>
                  <th>Check-Out</th>
                  <th>Reason</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {recent.map(r => {
                  const displayStatus = toDisplayStatus(r.status);
                  const checkIn  = r.punch_type !== "OUT" ? fmtTime12h(r.requested_in  ?? r.original_in)  : "—";
                  const checkOut = r.punch_type !== "IN"  ? fmtTime12h(r.requested_out ?? r.original_out) : "—";
                  return (
                    <tr key={r.id} onClick={() => setDetail(r)} style={{ cursor: "pointer" }}>
                      <td>{fmtSubmitted(r.date)}</td>
                      <td className="font-mono text-xs">{checkIn}</td>
                      <td className="font-mono text-xs">{checkOut}</td>
                      <td>{r.reason}</td>
                      <td style={{ textAlign: "center" }}>
                        <span className={STATUS_BADGE_CLASS[displayStatus]}>{STATUS_LABEL[displayStatus]}</span>
                      </td>
                      <td style={{ textAlign: "right" }} onClick={e => e.stopPropagation()}>
                        <button className="btn btn-ghost btn-sm" onClick={() => setDetail(r)} suppressHydrationWarning>
                          <i className="ti ti-eye" /> View
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showNew && (
        <RegularizationModal
          onClose={() => setShowNew(false)}
          onSuccess={refetch}
        />
      )}

      {detail && (
        <MyCorrectionDetailModal request={detail} onClose={() => setDetail(null)} />
      )}
    </div>
  );
}
