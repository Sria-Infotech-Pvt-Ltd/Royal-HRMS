"use client";

import { useState } from "react";
import { useClockWidget } from "@/hooks/useClockWidget";
import CorrectionModal from "@/app/dashboard/my-attendance/_components/CorrectionModal";
import FaceVerificationModal from "@/components/FaceVerificationModal";
import type { AttendanceMode, PunchLocation } from "@/types/attendance";

const MODE: AttendanceMode = "office";

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function todayString() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

interface Props {
  /** Called after a clock in/out request succeeds — lets the parent refresh
   *  any sibling widgets (KPIs, attendance status) that read the same data. */
  onPunchSuccess?: () => void;
}

export default function ClockInButton({ onPunchSuccess }: Props) {
  const {
    session, isLoading, isPunching, isLocating, faceVerificationRequired, prepareLocation, punch,
    isLockedOut, lockoutSecondsRemaining,
  } = useClockWidget();
  const [showModal, setShowModal] = useState(false);
  const [showFaceModal, setShowFaceModal] = useState(false);
  const [pendingLocation, setPendingLocation] = useState<PunchLocation | null>(null);

  const isClockedIn = session?.is_clocked_in ?? false;
  // isLocating covers prepareLocation()'s GPS acquisition + geofence-check
  // call — without it here, the button stayed clickable during that window,
  // letting a repeated click start a second, fully independent punch flow
  // (GPS + geofence + face capture + punch) stacked on top of the first.
  const isBusy      = isLoading || isPunching || isLocating || isLockedOut;

  async function handlePunch() {
    if (isLockedOut) return;
    // Location is fetched and geofence-validated BEFORE face verification —
    // same order the voice clock-in/out flow enforces.
    const { ok, location } = await prepareLocation(MODE);
    if (!ok) return;

    if (faceVerificationRequired) {
      setPendingLocation(location);
      setShowFaceModal(true);
      return;
    }
    const punchOk = await punch(isClockedIn ? "OUT" : "IN", MODE, location);
    if (punchOk) onPunchSuccess?.();
  }

  async function handleFaceCaptured(embedding: number[], livenessScore: number, captureSessionId: string) {
    setShowFaceModal(false);
    const ok = await punch(isClockedIn ? "OUT" : "IN", MODE, pendingLocation, embedding, livenessScore, captureSessionId);
    if (ok) onPunchSuccess?.();
  }

  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
        <button
          onClick={handlePunch}
          disabled={isBusy}
          style={{
            display: "inline-flex", alignItems: "center", gap: 7,
            padding: "7px 16px", borderRadius: 6,
            border: `1.5px solid ${isClockedIn ? "rgba(248,113,113,0.45)" : "rgba(74,222,128,0.45)"}`,
            cursor: isBusy ? "not-allowed" : "pointer",
            fontSize: 13, fontWeight: 700,
            background: isClockedIn ? "rgba(220,38,38,0.18)" : "rgba(22,163,74,0.18)",
            color: "#fff",
            opacity: isBusy ? 0.6 : 1,
            boxShadow: "0 2px 12px rgba(0,0,0,0.25)",
            transition: "background 0.15s, border-color 0.15s, transform 0.1s, opacity 0.15s",
            letterSpacing: "0.01em", whiteSpace: "nowrap",
          }}
          onMouseEnter={e => { if (!isBusy) (e.currentTarget as HTMLButtonElement).style.transform = "translateY(-1px)"; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.transform = "translateY(0)"; }}
        >
          {isLockedOut ? (
            <>
              <i className="ti ti-lock" style={{ fontSize: 14 }} />
              Try again in {formatCountdown(lockoutSecondsRemaining)}
            </>
          ) : isPunching ? (
            <>
              <i className="ti ti-loader-2" style={{ fontSize: 14, animation: "spin 1s linear infinite" }} />
              Please wait…
            </>
          ) : (
            <>
              <span style={{
                width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
                background: isClockedIn ? "#f87171" : "#4ade80",
                animation: !isClockedIn ? "clockPulse 2s ease-in-out infinite" : "none",
              }} />
              <i className={`ti ${isClockedIn ? "ti-clock-out" : "ti-clock-in"}`} style={{ fontSize: 14 }} />
              {isClockedIn ? "Clock Out" : "Clock In"}
            </>
          )}
        </button>

        <button
          onClick={() => setShowModal(true)}
          style={{
            display: "inline-flex", alignItems: "center", gap: 5,
            padding: 0, border: "none", background: "transparent",
            cursor: "pointer", fontSize: 11, fontWeight: 500,
            color: "rgba(255,255,255,0.65)",
            textDecoration: "underline", textDecorationColor: "rgba(255,255,255,0.3)",
            textUnderlineOffset: "2px", transition: "color 0.15s",
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.95)"; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.65)"; }}
        >
          <i className="ti ti-flag-3" style={{ fontSize: 11 }} />
          Request Attendance Correction
        </button>
      </div>

      <CorrectionModal
        isOpen={showModal}
        date={todayString()}
        onClose={() => setShowModal(false)}
        onSuccess={() => setShowModal(false)}
      />

      <FaceVerificationModal
        isOpen={showFaceModal}
        onCaptured={handleFaceCaptured}
        onClose={() => setShowFaceModal(false)}
      />
    </>
  );
}
