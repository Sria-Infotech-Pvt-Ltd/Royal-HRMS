"use client";

// "Activity history" card + the "Review visibility" note underneath it —
// both read-only, derived entirely from the review's own activity_history
// (see PerformanceReviewSerializer.get_activity_history, no separate audit
// model). Kept as one small file since neither piece has any state of its
// own.

import { formatDateTime } from "@/lib/formatDate";

export interface AppraisalActivityEntry {
  label: string;
  actor: string;
  at: string;
}

export default function AppraisalActivityHistory({ entries }: { entries: AppraisalActivityEntry[] }) {
  return (
    <>
      <div className="card mb-16">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-history" /> Activity history</div>
        </div>
        <div style={{ padding: "8px 20px 16px" }}>
          {entries.length === 0 ? (
            <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}>No activity recorded yet.</p>
          ) : (
            <div className="timeline">
              {entries.map((entry, idx) => (
                <div key={idx} className="tl-item">
                  <div className="tl-dot tl-neutral"><i className="ti ti-point" /></div>
                  <div className="tl-body">
                    <div className="tl-title">{entry.label} — {entry.actor}</div>
                    <div className="tl-desc">{formatDateTime(entry.at)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div style={{ padding: "16px 20px", display: "flex", gap: 10, alignItems: "flex-start" }}>
          <i className="ti ti-eye-off" style={{ color: "var(--on-variant)", marginTop: 2 }} />
          <p style={{ fontSize: 12, color: "var(--on-variant)", margin: 0 }}>
            Manager notes and calibrated ratings stay hidden until the outcome is published.
          </p>
        </div>
      </div>
    </>
  );
}
