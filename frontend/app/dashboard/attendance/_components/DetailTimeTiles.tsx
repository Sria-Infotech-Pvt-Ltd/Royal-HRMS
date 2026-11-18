"use client";

// The day's four numbers as tiles: clock in, clock out, total hours, overtime. A tile with no value shows a quiet dash.

import { PALETTE, tint } from "./attendancePalette";
import { isBlank } from "./attendanceView";

interface Props {
  clockIn: string;
  clockOut: string;
  totalHours: string;
  overtime: string;
}

interface Tile { label: string; value: string; icon: string; colour: string }

export default function DetailTimeTiles({ clockIn, clockOut, totalHours, overtime }: Props) {
  const tiles: Tile[] = [
    { label: "Clock in", value: clockIn, icon: "ti-login-2", colour: PALETTE.present },
    { label: "Clock out", value: clockOut, icon: "ti-logout-2", colour: PALETTE.half_day },
    { label: "Total hours", value: totalHours, icon: "ti-clock-hour-4", colour: PALETTE.on_leave },
    { label: "Overtime", value: overtime, icon: "ti-bolt", colour: PALETTE.late },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginBottom: 14 }}>
      {tiles.map(tile => {
        const blank = isBlank(tile.value);
        return (
          <div key={tile.label} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", borderRadius: 12, border: "1px solid var(--outline-v)", background: blank ? "var(--bg-low)" : tint(tile.colour, 0.08) }}>
            <span aria-hidden="true" style={{ width: 34, height: 34, borderRadius: 10, display: "grid", placeItems: "center", background: blank ? "var(--outline-v)" : tint(tile.colour, 0.18), color: blank ? "var(--outline)" : tile.colour, fontSize: 18 }}>
              <i className={`ti ${tile.icon}`} />
            </span>
            <span>
              <span style={{ display: "block", fontSize: 11.5, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".04em" }}>{tile.label}</span>
              <span style={{ display: "block", fontSize: 17, fontWeight: 800, fontFamily: "Menlo, Consolas, monospace", color: blank ? "var(--outline)" : "var(--on-bg)" }}>{blank ? "—" : tile.value}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}
