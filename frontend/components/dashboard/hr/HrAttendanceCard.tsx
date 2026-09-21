"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AttendanceToday, AttendancePunch } from "@/types/dashboard";

function formatSeconds(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h}h ${m}m`;
}

function modeLabel(mode: string): string {
  if (mode === "office") return "Office";
  if (mode === "wfh")    return "WFH";
  return mode.charAt(0).toUpperCase() + mode.slice(1);
}

export default function HrAttendanceCard() {
  const { data, loading } = useFetch<AttendanceToday>(API.attendance.today);

  const firstIn  = data?.punches.find((p: AttendancePunch) => p.type === "IN");
  const lastOut  = [...(data?.punches ?? [])].reverse().find((p: AttendancePunch) => p.type === "OUT");
  const isClockedIn = data?.is_clocked_in ?? false;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-clock-hour-4" /> My Attendance Today</div>
        {!loading && data && (
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 700,
            padding: "3px 10px", borderRadius: 20,
            background: isClockedIn ? "rgba(22,163,74,0.12)" : "rgba(220,38,38,0.10)",
            color:      isClockedIn ? "#16a34a"               : "#dc2626",
          }}>
            <span style={{ width: 5, height: 5, borderRadius: "50%", background: isClockedIn ? "#16a34a" : "#dc2626", flexShrink: 0 }} />
            {isClockedIn ? "Clocked In" : "Clocked Out"}
          </span>
        )}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : !data || data.punches.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center" }}>
          <i className="ti ti-clock-off" style={{ fontSize: 28, color: "var(--on-variant)", opacity: 0.4, display: "block", marginBottom: 8 }} />
          <div style={{ fontSize: 13, color: "var(--on-variant)" }}>Not clocked in yet</div>
        </div>
      ) : (
        <div style={{ padding: "12px 20px 16px" }}>
          {/* Stat tiles */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 14 }}>
            {[
              { icon: "ti-login",  label: "First Punch In",  val: firstIn?.time  ?? "—" },
              { icon: "ti-logout", label: "Last Punch Out",  val: lastOut?.time  ?? "—" },
              { icon: "ti-clock",  label: "Total Time",      val: data.total_seconds > 0 ? formatSeconds(data.total_seconds) : "—" },
            ].map(item => (
              <div key={item.label} style={{ padding: "10px 12px", borderRadius: 8, background: "var(--bg-high)", textAlign: "center" }}>
                <i className={`ti ${item.icon}`} style={{ fontSize: 18, color: "var(--primary)", display: "block", marginBottom: 4 }} />
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--on-bg)", lineHeight: 1 }}>{item.val}</div>
                <div style={{ fontSize: 10, color: "var(--on-variant)", marginTop: 3 }}>{item.label}</div>
              </div>
            ))}
          </div>

          {/* Punch log */}
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase", color: "var(--on-variant)", marginBottom: 6 }}>
            Punch Log
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {data.punches.map((punch: AttendancePunch, index: number) => (
              <div key={index} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 10px", borderRadius: 7, background: "var(--bg-high)" }}>
                <span style={{
                  width: 28, height: 28, borderRadius: 6, flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13,
                  background: punch.type === "IN" ? "rgba(22,163,74,0.15)" : "rgba(220,38,38,0.12)",
                  color:      punch.type === "IN" ? "#16a34a"               : "#dc2626",
                }}>
                  <i className={punch.type === "IN" ? "ti ti-login" : "ti ti-logout"} />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--on-bg)" }}>
                    {punch.type === "IN" ? "Punched In" : "Punched Out"} · {punch.time}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {punch.location}
                  </div>
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 10, whiteSpace: "nowrap",
                  background: "rgba(124,58,237,0.10)", color: "var(--primary)",
                }}>
                  {modeLabel(punch.attendance_mode)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
