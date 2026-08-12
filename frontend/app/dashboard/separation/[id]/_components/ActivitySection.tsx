"use client";

import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import type { SeparationActivityItem, SeparationRequest } from "@/types/separation";
import { fmtDateTime } from "../../_workflow";

function dotStyleFor(action: string | null | undefined): { dotClass: string; icon: string } {
  const a = (action ?? "").toLowerCase();
  if (a.includes("reject")) return { dotClass: "tl-error", icon: "ti-x" };
  if (a.includes("cancel")) return { dotClass: "tl-error", icon: "ti-ban" };
  if (a.includes("approve")) return { dotClass: "tl-success", icon: "ti-check" };
  return { dotClass: "tl-neutral", icon: "ti-point" };
}

export default function ActivitySection({ r }: { r: SeparationRequest }) {
  const { data: activities, loading } = useFetch<SeparationActivityItem[]>(API.separation.activities(r.id));
  const rows = [...(activities ?? [])].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-history" /> Activity</span>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {loading ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}><i className="ti ti-loader-2 spin" /> Loading…</p>
        ) : rows.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}>No activity recorded yet.</p>
        ) : (
          rows.map(entry => {
            const { dotClass, icon } = dotStyleFor(entry.action);
            const oldStatus = entry.old_status_display || entry.old_status;
            const newStatus = entry.new_status_display || entry.new_status;

            return (
              <div key={entry.id} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                <div className={`tl-dot ${dotClass}`} style={{ flexShrink: 0 }}>
                  <i className={`ti ${icon}`} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{entry.description}</span>
                    <span style={{ fontSize: 11, color: "var(--on-variant)", whiteSpace: "nowrap" }}>
                      {fmtDateTime(entry.created_at)}
                    </span>
                  </div>
                  {oldStatus && newStatus && (
                    <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                      Status: {oldStatus} → {newStatus}
                    </div>
                  )}
                  {entry.comment && (
                    <div style={{ fontSize: 12, color: "var(--on-variant)", background: "var(--bg-low)", borderRadius: 8, padding: "6px 10px", marginTop: 6 }}>
                      {entry.comment}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
