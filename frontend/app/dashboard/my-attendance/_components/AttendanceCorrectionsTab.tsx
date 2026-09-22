"use client";

import { useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import RegularizationModal from "./RegularizationModal";
import MyCorrectionDetailModal from "../../my-requests/_components/MyCorrectionDetailModal";
import {
  MyCorrectionRequest, PaginatedResponse, STATUS_BADGE_CLASS, STATUS_LABEL,
  toDisplayStatus,
} from "../../my-requests/_data";

const RECENT_COUNT = 5;

// "2 September correction" — day (no leading zero) + full month name, matching
// the reference copy pattern for a request row's title.
function correctionDateLabel(dateStr: string): string {
  if (!dateStr) return "Correction";
  const d = new Date(dateStr + "T12:00:00");
  if (isNaN(d.getTime())) return "Correction";
  return `${d.getDate()} ${d.toLocaleDateString("en-US", { month: "long" })} correction`;
}

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

      {/* The page-level "Regularize attendance" button (my-attendance/_client.tsx)
          already opens this same new-correction modal via autoOpenNew — the
          "Quick Actions" card that used to duplicate that single tile here
          was removed as a redundant second clickable for the same action. */}

      {error && <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error}</div>}

      {/* Attendance requests — latest 5; full history lives in My Requests */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title"><i className="ti ti-clock-edit" /> Attendance requests</div>
            <div className="page-sub" style={{ marginTop: 2 }}>Corrections remain visible beside original punches.</div>
          </div>
          <a href="/dashboard/my-requests?tab=attendance_correction" className="btn btn-ghost btn-sm">
            View All Corrections <i className="ti ti-arrow-right" />
          </a>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
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
            recent.map((r, idx) => {
              const displayStatus = toDisplayStatus(r.status);
              const approver = r.l2_approver_name || r.l1_approver_name || null;
              return (
                <div
                  key={r.id}
                  onClick={() => setDetail(r)}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "12px 20px", cursor: "pointer",
                    borderTop: idx === 0 ? "none" : "1px solid var(--outline-v)",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
                      {correctionDateLabel(r.date)}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                      {displayStatus === "approved" && approver
                        ? `Approved by ${approver}`
                        : STATUS_LABEL[displayStatus]} · View details
                    </div>
                  </div>
                  <span className={STATUS_BADGE_CLASS[displayStatus]}>{STATUS_LABEL[displayStatus].toUpperCase()}</span>
                </div>
              );
            })
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
