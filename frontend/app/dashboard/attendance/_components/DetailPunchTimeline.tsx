"use client";

// The day's punches as a timeline: in or out, the time, where it came from, and whether it was inside the office geofence.

import type { AttendanceDetailPunch } from "@/types/attendance";
import { PALETTE, tint } from "./attendancePalette";

const KIND: Record<string, { label: string; icon: string; colour: string }> = {
  IN: { label: "Clock In", icon: "ti-login-2", colour: PALETTE.present },
  OUT: { label: "Clock Out", icon: "ti-logout-2", colour: PALETTE.half_day },
  BOTH: { label: "In & Out", icon: "ti-arrows-exchange", colour: PALETTE.on_leave },
};

function Chip({ children }: { children: React.ReactNode }) {
  return <span style={{ fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 999, background: "var(--bg-low)", border: "1px solid var(--outline-v)", color: "var(--on-variant)" }}>{children}</span>;
}

function Geofence({ punch }: { punch: AttendanceDetailPunch }) {
  if (punch.is_geofence === true) return <span style={{ fontSize: 11.5, fontWeight: 600, color: PALETTE.present }}><i className="ti ti-circle-check" aria-hidden="true" /> Inside geofence</span>;
  if (punch.is_geofence === false) {
    return <span style={{ fontSize: 11.5, fontWeight: 600, color: PALETTE.absent }}><i className="ti ti-circle-x" aria-hidden="true" /> Outside geofence{punch.distance_m !== null ? ` · ${punch.distance_m.toFixed(0)} m away` : ""}</span>;
  }
  return <span style={{ fontSize: 11.5, color: "var(--outline)" }}><i className="ti ti-circle-dashed" aria-hidden="true" /> Geofence not applicable</span>;
}

export default function DetailPunchTimeline({ punches }: { punches: AttendanceDetailPunch[] }) {
  if (punches.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "26px 12px", color: "var(--on-variant)" }}>
        <i className="ti ti-fingerprint-off" aria-hidden="true" style={{ fontSize: 30, color: "var(--outline)" }} />
        <div style={{ fontSize: 13, marginTop: 6 }}>No punches recorded for this day.</div>
      </div>
    );
  }
  return (
    <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {punches.map((punch, index) => {
        const kind = KIND[punch.punch_type] ?? KIND.BOTH;
        return (
          <li key={index} style={{ display: "flex", gap: 12 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <span aria-hidden="true" style={{ width: 34, height: 34, borderRadius: "50%", display: "grid", placeItems: "center", background: tint(kind.colour, 0.16), color: kind.colour, fontSize: 17, flexShrink: 0 }}><i className={`ti ${kind.icon}`} /></span>
              {index < punches.length - 1 && <span aria-hidden="true" style={{ flex: 1, width: 2, background: "var(--outline-v)", margin: "4px 0" }} />}
            </div>
            <div style={{ paddingBottom: 16, flex: 1 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ fontWeight: 700, fontSize: 13.5, color: "var(--on-bg)" }}>{kind.label}</span>
                <span style={{ fontFamily: "Menlo, Consolas, monospace", fontWeight: 800, fontSize: 14, color: kind.colour }}>{punch.time}</span>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "5px 0" }}>
                <Chip>{punch.source}</Chip>
                <Chip>{punch.mode}</Chip>
              </div>
              <Geofence punch={punch} />
              {punch.face_fallback && (
                <div style={{ fontSize: 12, fontWeight: 600, color: PALETTE.late, marginTop: 4 }}>
                  <i className="ti ti-alert-triangle" aria-hidden="true" /> No Face ID: allowed by the Face ID fallback, please review
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
