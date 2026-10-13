"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { RecentPunchRow } from "@/types/attendance";

export default function RecentPunchesCard() {
  const { data, loading } = useFetch<RecentPunchRow[]>(API.attendance.recentPunches);
  const rows = data ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Recent punches</div>
          <div className="page-sub" style={{ marginTop: 2 }}>Device and web attendance events.</div>
        </div>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 0, padding: rows.length ? "4px 20px" : 20 }}>
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "16px 0", fontSize: 12.5, color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2 animate-spin" /> Loading…
          </div>
        ) : rows.length === 0 ? (
          <div style={{ textAlign: "center", padding: "24px 8px", color: "var(--on-variant)" }}>
            <i className="ti ti-clock-exclamation" style={{ fontSize: 28, color: "var(--outline-v)", display: "block", marginBottom: 8 }} />
            <div style={{ fontSize: 12.5 }}>No punches recorded yet.</div>
          </div>
        ) : (
          rows.map((row, i) => (
            <div
              key={i}
              style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "14px 0", borderBottom: i < rows.length - 1 ? "1px solid var(--outline-v)" : "none",
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: 13.5 }}>{row.date} · {row.location}</div>
                <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                  {row.clockIn ? `In ${row.clockIn}` : "No in-punch"}
                  {row.clockOut ? ` · Out ${row.clockOut}` : ` · ${row.source}`}
                </div>
              </div>
              <span className={`badge ${row.status === "PRESENT" ? "badge-success" : "badge-neutral"}`}>{row.status}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
