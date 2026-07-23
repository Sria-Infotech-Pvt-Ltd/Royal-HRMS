"use client";

import { useUpcomingTeamLeave } from "@/hooks/useManagerDashboard";

function initials(name: string): string {
  return name.split(" ").filter(Boolean).slice(0, 2).map(p => p[0]).join("").toUpperCase();
}

function fmtRange(start: string, end: string): string {
  const fmt = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return start === end ? fmt(start) : `${fmt(start)} – ${fmt(end)}`;
}

export default function ManagerUpcomingLeave() {
  const { data, loading } = useUpcomingTeamLeave();
  const items = data?.items ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar" /> Upcoming Leaves</div>
      </div>
      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : items.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          No upcoming leave scheduled for your team.
        </div>
      ) : (
        <div style={{ padding: 0 }}>
          {items.map(item => (
            <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 20px", borderBottom: "1px solid var(--bg-high)" }}>
              <div style={{ width: 32, height: 32, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 600, flexShrink: 0 }}>
                {initials(item.employee_name)}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{item.employee_name}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                  {fmtRange(item.start_date, item.end_date)} · {item.leave_type.replace(/_/g, " ")}
                </div>
              </div>
              <div style={{ fontSize: 11, color: "var(--outline)", textAlign: "right" }}>Approved</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
