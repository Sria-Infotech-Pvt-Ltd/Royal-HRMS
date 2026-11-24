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
import { tr } from "@/lib/i18n/tr";

const RECENT_COUNT = 5;

// "2 September correction" — day (no leading zero) + full month name, matching
// the reference copy pattern for a request row's title.
function correctionDateLabel(dateStr: string): string {
  if (!dateStr) return tr("Correction");
  const d = new Date(dateStr + "T12:00:00");
  if (isNaN(d.getTime())) return tr("Correction");
  return tr("{day} {month} correction", { day: d.getDate(), month: d.toLocaleDateString("en-US", { month: "long" }) });
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

  const recent = corrections.slice(0, RECENT_COUNT);

  return (
    <>
      {/* The page-level "Regularize attendance" button (my-attendance/_client.tsx)
          already opens this same new-correction modal via autoOpenNew — the
          "Quick Actions" card that used to duplicate that single tile here
          was removed as a redundant second clickable for the same action. */}

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      {/* Attendance requests — latest 5; full history lives in My Requests */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title"><i className="ti ti-clock-edit" /> {tr("Attendance requests")}</div>
            <div className="page-sub" style={{ marginTop: 2 }}>{tr("Corrections remain visible beside original punches.")}</div>
          </div>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {loading ? (
            <div style={{ padding: "24px 20px", textAlign: "center" }}>
              <i className="ti ti-loader-2 spin" style={{ fontSize: 20, color: "var(--primary)" }} />
            </div>
          ) : recent.length === 0 ? (
            <div className="empty-state" style={{ padding: "24px 20px" }}>
              <i className="ti ti-clock-edit" style={{ fontSize: 28, marginBottom: 8 }} />
              <h3 style={{ fontSize: 13.5 }}>{tr("No correction requests yet")}</h3>
              <p>{tr("Use Request Attendance Correction above if a punch was missed or recorded incorrectly.")}</p>
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
                    padding: "10px 20px", cursor: "pointer",
                    borderTop: idx === 0 ? "none" : "1px solid var(--outline-v)",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--on-bg)" }}>
                      {correctionDateLabel(r.date)}
                    </div>
                    <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2 }}>
                      {displayStatus === "approved" && approver
                        ? tr("Approved by {approver}", { approver: approver })
                        : tr(STATUS_LABEL[displayStatus])} · {tr("View details")}
                    </div>
                  </div>
                  <span className={STATUS_BADGE_CLASS[displayStatus]}>{tr(STATUS_LABEL[displayStatus]).toUpperCase()}</span>
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
    </>
  );
}
