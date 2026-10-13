"use client";

// Left-column "My requests" preview — renders the same MyRequestItem shape
// and status badges as the My Requests tab (app/dashboard/my-requests), just
// the 5 most recent. HomeTab.tsx does the fetching/normalising via the
// shared helpers in my-requests/_data.ts; this component only renders.

import { DisplayStatus, MyRequestItem, STATUS_BADGE_CLASS, STATUS_LABEL, TYPE_META, fmtSubmitted } from "../../my-requests/_data";

interface Props {
  items: MyRequestItem[];
  onViewAll: () => void;
}

export default function HomeRequestsList({ items, onViewAll }: Props) {
  return (
    <div className="card">
      <div className="card-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div className="card-title"><i className="ti ti-list-check" /> My requests</div>
        <button onClick={onViewAll} className="btn btn-ghost btn-sm">
          View all <i className="ti ti-arrow-right" />
        </button>
      </div>

      {items.length === 0 ? (
        <div className="empty-state" style={{ padding: "32px 20px" }}>
          <i className="ti ti-inbox" />
          <p>No requests yet.</p>
        </div>
      ) : (
        <div>
          {items.map(item => {
            const meta = TYPE_META[item.kind];
            const status: DisplayStatus = item.displayStatus;
            return (
              <div
                key={item.key}
                onClick={onViewAll}
                style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 20px", borderBottom: "1px solid var(--outline-v)", cursor: "pointer" }}
              >
                <i className={`ti ${meta.icon}`} style={{ fontSize: 16, color: meta.color, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="font-mono" style={{ fontSize: 11, color: "var(--on-variant)" }}>{item.requestCode}</span>
                    <span style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{item.title}</span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{fmtSubmitted(item.submittedAt)}</div>
                </div>
                <span className={STATUS_BADGE_CLASS[status]} style={{ flexShrink: 0 }}>{STATUS_LABEL[status]}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
