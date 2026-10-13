"use client";

// "My requests" card — the most recent submissions across leave, expense,
// attendance-correction and work-from-home, each opening the Requests tab.

import { MyRequestItem, STATUS_LABEL, fmtSubmitted } from "../../my-requests/_data";

interface Props {
  items: MyRequestItem[];
  onViewAll: () => void;
}

export default function HomeRequestsList({ items, onViewAll }: Props) {
  return (
    <section className="ess-card">
      <div className="ess-pagehead">
        <div><h2>My requests</h2><p>Recent submissions and approval progress.</p></div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onViewAll}>View all</button>
      </div>
      <div className="ess-list">
        {items.length === 0 ? (
          <div className="ess-row"><div><b>No requests yet</b><small>Leave, expense and attendance requests you submit appear here.</small></div></div>
        ) : items.map(item => (
          <div key={item.key} className="ess-row">
            <button type="button" className="ess-row ess-row-link" onClick={onViewAll}>
              <div><b>{item.requestCode} · {item.title}</b><small>{fmtSubmitted(item.submittedAt)}</small></div>
              <span className="row-go" aria-hidden="true">›</span>
            </button>
            <span className={`state${item.displayStatus === "pending" ? "" : " ok"}`}>{STATUS_LABEL[item.displayStatus].toUpperCase()}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
