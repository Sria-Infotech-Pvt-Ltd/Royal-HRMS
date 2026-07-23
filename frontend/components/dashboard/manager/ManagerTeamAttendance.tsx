"use client";

import { useTeamAttendanceToday } from "@/hooks/useManagerDashboard";

const STATUS_BADGE: Record<string, string> = {
  present:     "badge-success",
  late:        "badge-error",
  incomplete:  "badge-success",
  half_day:    "badge-info",
  on_leave:    "badge-warn",
  weekly_off:  "badge-neutral",
  holiday:     "badge-neutral",
  absent:      "badge-error",
  not_marked:  "badge-neutral",
};

function initials(name: string): string {
  return name.split(" ").filter(Boolean).slice(0, 2).map(p => p[0]).join("").toUpperCase();
}

export default function ManagerTeamAttendance() {
  const { data, loading } = useTeamAttendanceToday();
  const rows = data?.rows ?? [];

  return (
    <div className="card mb-16">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-users" /> Team Attendance Today</div>
        {!loading && data && (
          <span className="badge badge-success">{data.present_count}/{data.team_size} present</span>
        )}
      </div>
      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : rows.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          No direct reports found.
        </div>
      ) : (
        <div style={{ padding: 0 }}>
          {rows.map(row => (
            <div key={row.employee_id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 20px", borderBottom: "1px solid var(--bg-high)" }}>
              <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 600, flexShrink: 0 }}>
                {initials(row.employee_name)}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{row.employee_name}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{row.first_punch_in ?? "—"}</div>
              </div>
              <span className={`badge ${STATUS_BADGE[row.status] ?? "badge-neutral"}`}>{row.status_display}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
