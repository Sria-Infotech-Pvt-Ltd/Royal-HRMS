"use client";

import { useState } from "react";
import { useClockWidget } from "@/hooks/useClockWidget";
import { useTodayAttendanceMode } from "@/hooks/useTodayAttendanceMode";
import FaceVerificationModal from "@/components/FaceVerificationModal";
import { formatLockoutCountdown } from "@/lib/faceApi/lockout";
import type { PunchLocation } from "@/types/attendance";
import { useAfterMount } from "@/hooks/useAfterMount";
import { tr } from "@/lib/i18n/tr";

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
  if (isInside === true)  return { color: "var(--success)", title: tr("Inside geofence")  };
  if (isInside === false) return { color: "var(--error)",   title: tr("Outside geofence") };
  return { color: "var(--outline)", title: tr("Geofence N/A") };
}

function browserDate(): string {
  return new Date().toDateString();
}

export default function ClockWidget() {
  const clientDate = useAfterMount(browserDate, "");
  const {
    session, isLoading, isPunching, isLocating, faceVerificationRequired, prepareLocation, punch,
    ensureFaceReady, isLockedOut, lockoutSecondsRemaining,
  } = useClockWidget();
  const [showFaceModal, setShowFaceModal] = useState(false);
  const [pendingLocation, setPendingLocation] = useState<PunchLocation | null>(null);

  // No manual office/WFH toggle: the mode follows whether today is inside an approved WFH request (see useTodayAttendanceMode).
  const MODE = useTodayAttendanceMode();

  const isClockedIn = session?.is_clocked_in ?? false;

  async function handlePunch() {
    // Not registered / pending / rejected: stop here with the server's instruction. No location request, no camera.
    if (!ensureFaceReady()) return;

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
            {session?.date_display ?? clientDate}
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
            {isClockedIn ? tr("Punched In") : tr("Punched Out")}
          </span>
          {MODE === "wfh" && (
            <span
              title={tr("You have an approved Work From Home request for today")}
              style={{
                display: "inline-flex", alignItems: "center", gap: 5, marginLeft: 8,
                padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
                background: "var(--primary-c)", color: "var(--primary)",
              }}
            >
              <i className="ti ti-home-2" style={{ fontSize: 11 }} /> {tr("WFH Today")}
            </span>
          )}
        </div>

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 26, fontWeight: 700, fontVariantNumeric: "tabular-nums", color: "var(--on-bg)", lineHeight: 1.1 }}>
            {fmtTimer(session?.session_seconds ?? 0)}
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
            {tr("Total today:")} <span style={{ fontWeight: 600, color: "var(--on-bg)" }}>{fmtTotal(session?.total_seconds ?? 0)}</span>
          </div>
        </div>

        <button
          onClick={handlePunch}
          disabled={isPunching || isLockedOut}
          style={{
            width: "100%", height: 44, borderRadius: 8, border: "none", cursor: isPunching || isLockedOut ? "not-allowed" : "pointer",
            background: isClockedIn ? "var(--error)" : "var(--success)",
            color: "#fff", fontSize: 14, fontWeight: 700, marginBottom: 16,
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            opacity: isPunching || isLockedOut ? 0.7 : 1, transition: "background 0.15s, opacity 0.15s",
          }}
        >
          {isLockedOut
            ? <><i className="ti ti-lock" /> {tr("Please wait")} {formatLockoutCountdown(lockoutSecondsRemaining)}</>
            : isLocating
            ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> {tr("Getting location…")}</>
            : isPunching
            ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> {tr("Please wait…")}</>
            : <><i className={`ti ${isClockedIn ? "ti-clock-out" : "ti-clock-in"}`} /> {isClockedIn ? tr("Punch Out") : tr("Punch In")}</>}
        </button>

        {displayPunches.length > 0 && (
          <div>
            <div style={{ fontSize: 10, fontWeight: 600, color: "var(--on-variant)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.06em" }}>{tr("Punch Log")}</div>
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
