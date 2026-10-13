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
  note?: string;
}

export default function AppraisalActivityHistory({ entries }: { entries: AppraisalActivityEntry[] }) {
  return (
    <>
      <div className="card mb-16">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-history" /> Activity history</div>
        </div>
        <div style={{ padding: "0 20px 4px" }}>
          <p style={{ margin: 0, fontSize: 12.5, color: "var(--on-variant)" }}>
            Each stage change is recorded in this browser-local demo.
          </p>
        </div>
        <div style={{ padding: "8px 20px 16px" }}>
          {entries.length === 0 ? (
            <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}>No activity recorded yet.</p>
          ) : (
            <div className="timeline">
              {entries.map((entry, idx) => (
                <div key={idx} className="tl-item">
                  <div className="tl-dot tl-success"><i className="ti ti-check" /></div>
                  <div className="tl-body">
                    <div className="tl-title">{entry.label}</div>
                    <div className="tl-desc">
                      {entry.actor} · {formatDateTime(entry.at)}{entry.note ? ` · ${entry.note}` : ""}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div>
        <div style={{ fontWeight: 700, fontSize: 13 }}>Review visibility</div>
        <p style={{ fontSize: 12, color: "var(--on-variant)", margin: "4px 0 0" }}>
          Manager notes and calibrated ratings stay hidden until the outcome is published. This demo does not affect payroll or promotion changes.
        </p>
      </div>
    </>
  );
}
