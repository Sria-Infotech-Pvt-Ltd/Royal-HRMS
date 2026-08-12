"use client";

import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import type { SeparationActivityItem, SeparationRequest } from "@/types/separation";
import { fmtDateTime } from "../../_workflow";

export default function ActivitySection({ r }: { r: SeparationRequest }) {
  const { data: activities, loading } = useFetch<SeparationActivityItem[]>(API.separation.activities(r.id));
  const rows = activities ?? [];

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
          rows.map(entry => (
            <div key={entry.id} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              <div className="tl-dot tl-neutral" style={{ flexShrink: 0 }}>
                <i className="ti ti-point" />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
                    {entry.action || entry.description || "Activity"}
                  </span>
                  <span style={{ fontSize: 11, color: "var(--on-variant)", whiteSpace: "nowrap" }}>
                    {fmtDateTime(entry.created_at || entry.at)}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>{entry.by_name || entry.actor_name}</div>
                {entry.note && (
                  <div style={{ fontSize: 12, color: "var(--on-variant)", background: "var(--bg-low)", borderRadius: 8, padding: "6px 10px", marginTop: 6 }}>
                    {entry.note}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
