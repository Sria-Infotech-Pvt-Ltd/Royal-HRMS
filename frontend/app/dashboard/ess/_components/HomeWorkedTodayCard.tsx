"use client";

// Home-page card showing today's worked time once the employee has punched in:
// a live timer for the current session plus the total for the day. Display
// only — punching itself stays on the hero button.

import { useWorkedToday } from "@/hooks/useWorkedToday";
import type { AttendanceStatus } from "@/types/employeeDashboard";

interface Props {
  status: AttendanceStatus | null;
}

function formatTimer(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `${hours}h ${String(minutes).padStart(2, "0")}m ${String(seconds).padStart(2, "0")}s`;
}

function formatTotal(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  return `${hours}h ${String(minutes).padStart(2, "0")}m`;
}

interface PunchTimeProps {
  label: string;
  time: string | null;
  tone: string;
}

function PunchTime({ label, time, tone }: PunchTimeProps) {
  return (
    <div style={{ background: "var(--bg-low)", borderRadius: 8, padding: "6px 12px", minWidth: 84 }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.05em", color: tone }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, fontVariantNumeric: "tabular-nums", color: "var(--on-bg)", marginTop: 2 }}>{time ?? "—"}</div>
    </div>
  );
}

export default function HomeWorkedTodayCard({ status }: Props) {
  const refreshKey = `${status?.clocked_in ?? ""}|${status?.clock_in_time ?? ""}|${status?.clock_out_time ?? ""}`;
  const { isLoading, isClockedIn, sessionSeconds, totalSeconds, punches } = useWorkedToday(refreshKey);

  // Nothing to show until there has been a punch today.
  if (isLoading || punches.length === 0) return null;

  // First punch-in of the day; the last punch-out only counts once the employee is actually out.
  const firstIn = punches.find(punch => punch.type === "IN");
  const lastOut = [...punches].reverse().find(punch => punch.type === "OUT");

  return (
    <div className="card" style={{ padding: "16px 20px", marginBottom: 14, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
      <div>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em", display: "flex", alignItems: "center", gap: 6 }}>
          <i className="ti ti-clock-hour-4" /> TIME WORKED TODAY
        </div>
        <div style={{ fontSize: 26, fontWeight: 700, fontVariantNumeric: "tabular-nums", color: "var(--on-bg)", lineHeight: 1.15, marginTop: 4 }}>
          {formatTimer(isClockedIn ? sessionSeconds : totalSeconds)}
        </div>
        <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
          {isClockedIn
            ? <>Current session · total today <b style={{ color: "var(--on-bg)" }}>{formatTotal(totalSeconds)}</b></>
            : "Punched out · total for today"}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <PunchTime label="PUNCH IN" time={firstIn?.time ?? null} tone="var(--success)" />
        <PunchTime label="PUNCH OUT" time={isClockedIn ? null : (lastOut?.time ?? null)} tone="var(--error)" />
        <span
          style={{
            display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
            background: isClockedIn ? "var(--success-c)" : "var(--bg-low)",
            color: isClockedIn ? "var(--success)" : "var(--on-variant)",
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor", display: "inline-block", animation: isClockedIn ? "clockPulse 2s ease-in-out infinite" : "none" }} />
          {isClockedIn ? "Punched In" : "Punched Out"}
        </span>
      </div>
    </div>
  );
}
