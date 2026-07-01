"use client";

import { useState, useEffect, useCallback } from "react";
import RegularizationModal from "@/app/dashboard/my-attendance/_components/RegularizationModal";

interface PunchEntry {
  type: "IN" | "OUT";
  time: string;
  location: string;
}

const INITIAL_PUNCHES: PunchEntry[] = [
  { type: "IN", time: "09:00", location: "Chennai HQ · Biometric" },
];

function formatDuration(s: number) {
  const h = String(Math.floor(s / 3600)).padStart(2, "0");
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const sec = String(s % 60).padStart(2, "0");
  return `${h}:${m}:${sec}`;
}

export default function ClockWidget() {
  const [now, setNow]                     = useState<Date | null>(null);
  const [isClockedIn, setIsClockedIn]     = useState(true);
  const [punches, setPunches]             = useState<PunchEntry[]>(INITIAL_PUNCHES);
  const [totalSeconds, setTotalSeconds]   = useState(9 * 3600 + 24 * 60 + 17);
  const [sessionSeconds, setSessionSeconds] = useState(24 * 60 + 17);
  const [showRegularize, setShowRegularize] = useState(false);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => {
      setNow(new Date());
      setTotalSeconds(v => v + 1);
    }, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!isClockedIn) return;
    const id = setInterval(() => setSessionSeconds(v => v + 1), 1000);
    return () => clearInterval(id);
  }, [isClockedIn]);

  const handleClockToggle = useCallback(() => {
    const time = new Date().toLocaleTimeString("en-IN", {
      hour: "2-digit", minute: "2-digit", hour12: false,
    });
    if (isClockedIn) {
      setPunches(prev => [...prev, { type: "OUT", time, location: "Chennai HQ · Biometric" }]);
      setIsClockedIn(false);
    } else {
      setPunches(prev => [...prev, { type: "IN", time, location: "Chennai HQ · Biometric" }]);
      setIsClockedIn(true);
      setSessionSeconds(0);
    }
  }, [isClockedIn]);

  const wallClock = now
    ? now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true })
    : "--:--:--";
  const dateStr = now
    ? now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
    : "";

  return (
    <>
      <div className="card" style={{ overflow: "hidden" }}>

        {/* Header — live wall clock */}
        <div style={{
          background: "linear-gradient(135deg, var(--primary) 0%, #1a3a6e 100%)",
          padding: "22px 20px 18px",
          textAlign: "center",
          color: "#fff",
        }}>
          <div
            suppressHydrationWarning
            style={{
              fontSize: 30,
              fontWeight: 300,
              fontVariantNumeric: "tabular-nums",
              letterSpacing: "0.06em",
              fontFamily: "Menlo, Consolas, monospace",
              lineHeight: 1,
              marginBottom: 6,
            }}
          >
            {wallClock}
          </div>
          <div suppressHydrationWarning style={{ fontSize: 12, color: "rgba(255,255,255,0.6)", marginBottom: 16 }}>
            {dateStr}
          </div>

          {/* Status pill */}
          <div style={{ display: "flex", justifyContent: "center" }}>
            <div style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              background: isClockedIn ? "rgba(74,222,128,0.15)" : "rgba(255,255,255,0.10)",
              border: `1px solid ${isClockedIn ? "rgba(74,222,128,0.4)" : "rgba(255,255,255,0.2)"}`,
              borderRadius: 20,
              padding: "5px 14px",
              fontSize: 12,
              fontWeight: 600,
              color: isClockedIn ? "#86efac" : "rgba(255,255,255,0.6)",
            }}>
              <span style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: isClockedIn ? "#4ade80" : "rgba(255,255,255,0.4)",
                animation: isClockedIn ? "clockPulse 2s ease-in-out infinite" : "none",
                display: "inline-block",
                flexShrink: 0,
              }} />
              {isClockedIn ? "Clocked In" : "Clocked Out"}
            </div>
          </div>
        </div>

        <div className="card-body" style={{ paddingTop: 16, paddingBottom: 16 }}>

          {/* Session + Total duration */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "1fr 1px 1fr",
            background: "var(--bg)",
            borderRadius: 8,
            marginBottom: 14,
            overflow: "hidden",
          }}>
            <div style={{ padding: "10px 12px", textAlign: "center" }}>
              <div style={{ fontSize: 10, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4, fontWeight: 600 }}>
                Session
              </div>
              <div style={{
                fontFamily: "Menlo, Consolas, monospace",
                fontSize: 18,
                fontWeight: 700,
                color: isClockedIn ? "var(--success)" : "var(--on-variant)",
                fontVariantNumeric: "tabular-nums",
              }}>
                {formatDuration(sessionSeconds)}
              </div>
            </div>
            <div style={{ background: "var(--outline-v)" }} />
            <div style={{ padding: "10px 12px", textAlign: "center" }}>
              <div style={{ fontSize: 10, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4, fontWeight: 600 }}>
                Total Today
              </div>
              <div style={{
                fontFamily: "Menlo, Consolas, monospace",
                fontSize: 18,
                fontWeight: 700,
                color: "var(--on-bg)",
                fontVariantNumeric: "tabular-nums",
              }}>
                {formatDuration(totalSeconds)}
              </div>
            </div>
          </div>

          {/* Clock In / Clock Out button */}
          <button
            onClick={handleClockToggle}
            style={{
              width: "100%",
              height: 46,
              borderRadius: 10,
              border: "none",
              cursor: "pointer",
              background: isClockedIn
                ? "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)"
                : "linear-gradient(135deg, #22c55e 0%, #16a34a 100%)",
              color: "#fff",
              fontSize: 15,
              fontWeight: 700,
              marginBottom: 14,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              boxShadow: isClockedIn
                ? "0 4px 14px rgba(239,68,68,0.30)"
                : "0 4px 14px rgba(34,197,94,0.30)",
              transition: "opacity 0.15s",
              letterSpacing: "0.02em",
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.opacity = "0.88"; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.opacity = "1"; }}
          >
            <i className={`ti ${isClockedIn ? "ti-clock-out" : "ti-clock-in"}`} style={{ fontSize: 18 }} />
            {isClockedIn ? "Clock Out" : "Clock In"}
          </button>

          {/* Punch timeline */}
          {punches.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8, fontWeight: 600 }}>
                Today&apos;s Punches
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                {punches.map((p, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "8px 10px",
                      background: "var(--bg)",
                      borderRadius: 7,
                      borderLeft: `3px solid ${p.type === "IN" ? "var(--success)" : "var(--error)"}`,
                    }}
                  >
                    <i
                      className={`ti ${p.type === "IN" ? "ti-login" : "ti-logout"}`}
                      style={{ fontSize: 13, color: p.type === "IN" ? "var(--success)" : "var(--error)", flexShrink: 0 }}
                    />
                    <span style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 13, fontWeight: 600, color: "var(--on-bg)", minWidth: 38 }}>
                      {p.time}
                    </span>
                    <span style={{ fontSize: 11, color: "var(--on-variant)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {p.location}
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 700, color: p.type === "IN" ? "var(--success)" : "var(--error)", flexShrink: 0 }}>
                      {p.type}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Attendance correction */}
          <button
            onClick={() => setShowRegularize(true)}
            className="btn btn-ghost"
            style={{ width: "100%", fontSize: 12, height: 34, gap: 6 }}
          >
            <i className="ti ti-flag-3" />
            Request Attendance Correction
          </button>
        </div>
      </div>

      {showRegularize && <RegularizationModal onClose={() => setShowRegularize(false)} />}
    </>
  );
}
