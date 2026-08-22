"use client";

import { useState } from "react";
import { useClockWidget } from "@/hooks/useClockWidget";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import FaceVerificationModal from "@/components/FaceVerificationModal";
import type { PunchLocation } from "@/types/attendance";
import type { WorkFromHomeRequest } from "@/types/workFromHome";

// Local calendar date, not UTC (Date.toISOString() would misdate the hours
// just after local midnight, e.g. 12:30 AM IST is still UTC "yesterday" —
// the exact case an employee clocking in right after midnight would hit).
function localDateString(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function isTodayWithin(r: WorkFromHomeRequest): boolean {
  const today = localDateString(new Date());
  return r.start_date <= today && today <= r.end_date;
}

function fmtTimer(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
}

function fmtTotal(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${String(m).padStart(2, "0")}m`;
}

function geofenceDot(isInside: boolean | null) {
  if (isInside === true)  return { color: "var(--success)", title: "Inside geofence"  };
  if (isInside === false) return { color: "var(--error)",   title: "Outside geofence" };
  return { color: "var(--outline)", title: "Geofence N/A" };
}

export default function ClockWidget() {
  const { session, isLoading, isPunching, isLocating, faceVerificationRequired, prepareLocation, punch } = useClockWidget();
  const [showFaceModal, setShowFaceModal] = useState(false);
  const [pendingLocation, setPendingLocation] = useState<PunchLocation | null>(null);

  // No manual office/WFH toggle — mode is derived automatically from whether
  // today falls inside one of the employee's own approved WFH requests.
  // Server-side validation (services_geofencing.py's wfh strategy) is the
  // real gate either way; this only decides which validation path a punch
  // goes through, so it doesn't need to be authoritative.
  const { data: wfhData } = useFetch<{ results: WorkFromHomeRequest[] }>(
    `${API.workFromHome.requests}?status=approved&page_size=5`,
  );
  const MODE = (wfhData?.results ?? []).some(isTodayWithin) ? "wfh" : "office";

  const isClockedIn = session?.is_clocked_in ?? false;

  async function handlePunch() {
    // Location is fetched and geofence-validated BEFORE face verification —
    // same order the voice clock-in/out flow enforces.
    const { ok, location } = await prepareLocation(MODE);
    if (!ok) return;

    if (faceVerificationRequired) {
      setPendingLocation(location);
      setShowFaceModal(true);
      return;
    }
    await punch(isClockedIn ? "OUT" : "IN", MODE, location);
  }

  async function handleFaceCaptured(embedding: number[], livenessScore: number, captureSessionId: string) {
    setShowFaceModal(false);
    await punch(isClockedIn ? "OUT" : "IN", MODE, pendingLocation, embedding, livenessScore, captureSessionId);
  }

  const punches    = session?.punches ?? [];
  const latestIn   = [...punches].reverse().find(p => p.type === "IN");
  const latestOut  = [...punches].reverse().find(p => p.type === "OUT");
  const displayPunches = [latestIn, latestOut].filter((p): p is NonNullable<typeof p> => Boolean(p));

  if (isLoading) {
    return (
      <div className="card" style={{ padding: 24, minHeight: 220, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite", color: "var(--primary)" }} />
      </div>
    );
  }

  return (
    <>
      <div className="card" style={{ padding: 24 }}>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 6 }}>
            {session?.date_display ?? new Date().toDateString()}
          </div>
          <span
            style={{
              display: "inline-flex", alignItems: "center", gap: 5,
              padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
              background: isClockedIn ? "var(--success-c)" : "var(--bg-low)",
              color: isClockedIn ? "var(--success)" : "var(--on-variant)",
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor", display: "inline-block", animation: isClockedIn ? "clockPulse 2s ease-in-out infinite" : "none" }} />
            {isClockedIn ? "Clocked In" : "Clocked Out"}
          </span>
          {MODE === "wfh" && (
            <span
              title="You have an approved Work From Home request for today"
              style={{
                display: "inline-flex", alignItems: "center", gap: 5, marginLeft: 8,
                padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
                background: "var(--primary-c)", color: "var(--primary)",
              }}
            >
              <i className="ti ti-home-2" style={{ fontSize: 11 }} /> WFH Today
            </span>
          )}
        </div>

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 26, fontWeight: 700, fontVariantNumeric: "tabular-nums", color: "var(--on-bg)", lineHeight: 1.1 }}>
            {fmtTimer(session?.session_seconds ?? 0)}
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
            Total today: <span style={{ fontWeight: 600, color: "var(--on-bg)" }}>{fmtTotal(session?.total_seconds ?? 0)}</span>
          </div>
        </div>

        <button
          onClick={handlePunch}
          disabled={isPunching}
          style={{
            width: "100%", height: 44, borderRadius: 8, border: "none", cursor: isPunching ? "not-allowed" : "pointer",
            background: isClockedIn ? "var(--error)" : "var(--success)",
            color: "#fff", fontSize: 14, fontWeight: 700, marginBottom: 16,
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            opacity: isPunching ? 0.7 : 1, transition: "background 0.15s, opacity 0.15s",
          }}
        >
          {isLocating
            ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Getting location…</>
            : isPunching
            ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Please wait…</>
            : <><i className={`ti ${isClockedIn ? "ti-clock-out" : "ti-clock-in"}`} /> {isClockedIn ? "Clock Out" : "Clock In"}</>}
        </button>

        {displayPunches.length > 0 && (
          <div>
            <div style={{ fontSize: 10, fontWeight: 600, color: "var(--on-variant)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.06em" }}>Punch Log</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {displayPunches.map((p, i) => {
                const dot = geofenceDot(p.is_inside_geofence);
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, padding: "4px 8px", background: "var(--bg-low)", borderRadius: 6 }}>
                    <span style={{ fontWeight: 700, color: p.type === "IN" ? "var(--success)" : "var(--error)", minWidth: 30 }}>{p.type}</span>
                    <span style={{ fontFamily: "Menlo, Consolas, monospace", color: "var(--on-bg)" }}>{p.time}</span>
                    <span title={dot.title} style={{ width: 7, height: 7, borderRadius: "50%", background: dot.color, display: "inline-block", flexShrink: 0 }} />
                    <span style={{ color: "var(--on-variant)", fontSize: 11 }}>{p.attendance_mode}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <FaceVerificationModal
        isOpen={showFaceModal}
        onCaptured={handleFaceCaptured}
        onClose={() => setShowFaceModal(false)}
      />
    </>
  );
}
