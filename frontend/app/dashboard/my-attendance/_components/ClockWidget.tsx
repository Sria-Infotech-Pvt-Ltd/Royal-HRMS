"use client";

import { useState, useEffect } from "react";
import RegularizationModal from "./RegularizationModal";

interface PunchEntry {
  type: "IN" | "OUT";
  time: string;
  location: string;
}

const INITIAL_PUNCHES: PunchEntry[] = [
  { type: "IN", time: "09:00", location: "Chennai HQ · Biometric" },
];

export default function ClockWidget() {
  const [isClockedIn, setIsClockedIn] = useState(true);
  const [punches, setPunches] = useState<PunchEntry[]>(INITIAL_PUNCHES);
  const [showRegularize, setShowRegularize] = useState(false);
  const [totalSeconds, setTotalSeconds] = useState(9 * 3600 + 24 * 60 + 17);
  const [sessionSeconds, setSessionSeconds] = useState(24 * 60 + 17);

  useEffect(() => {
    const interval = setInterval(() => {
      setTotalSeconds(v => v + 1);
      if (isClockedIn) setSessionSeconds(v => v + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isClockedIn]);

  function formatTime(s: number) {
    const h = String(Math.floor(s / 3600)).padStart(2, "0");
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    const sec = String(s % 60).padStart(2, "0");
    return `${h}:${m}:${sec}`;
  }

  function handleClockToggle() {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    if (isClockedIn) {
      setPunches(prev => [...prev, { type: "OUT", time, location: "Chennai HQ · Biometric" }]);
      setIsClockedIn(false);
    } else {
      setPunches(prev => [...prev, { type: "IN", time, location: "Chennai HQ · Biometric" }]);
      setIsClockedIn(true);
      setSessionSeconds(0);
    }
  }

  return (
    <>
      <div className="card" style={{ overflow: "hidden" }}>
        {/* Clock header */}
        <div style={{ background: "var(--primary)", padding: "18px 20px", textAlign: "center", color: "#fff" }}>
          <div style={{ fontSize: 36, fontWeight: 300, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.01em", fontFamily: "Menlo, Consolas, monospace" }}>
            {formatTime(totalSeconds)}
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.65)", marginTop: 4 }}>
            Monday, 30 June 2025
          </div>
        </div>

        <div className="card-body">
          {/* Session info */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 10, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                {isClockedIn ? "Session Active" : "Session Ended"}
              </div>
              <div style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 17, fontWeight: 600, color: isClockedIn ? "var(--success)" : "var(--on-variant)" }}>
                {formatTime(sessionSeconds)}
              </div>
            </div>
            <span className={`badge ${isClockedIn ? "badge-success" : "badge-neutral"}`}>
              {isClockedIn ? "● Clocked In" : "○ Clocked Out"}
            </span>
          </div>

          {/* Clock in/out button */}
          <button
            onClick={handleClockToggle}
            style={{
              width: "100%", height: 42, borderRadius: 8, border: "none", cursor: "pointer",
              background: isClockedIn ? "var(--error)" : "var(--success)",
              color: "#fff", fontSize: 14, fontWeight: 600, marginBottom: 12,
              display: "flex", alignItems: "center", justifyContent: "center", gap: 7,
              transition: "background 0.15s",
            }}
          >
            <i className={`ti ${isClockedIn ? "ti-clock-out" : "ti-clock-in"}`} />
            {isClockedIn ? "Clock Out" : "Clock In"}
          </button>

          {/* Punch list */}
          <div style={{ display: "flex", flexDirection: "column", gap: 5, marginBottom: 12 }}>
            {punches.map((p, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 10px", background: "var(--bg)", borderRadius: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: p.type === "IN" ? "var(--success)" : "var(--error)", width: 28 }}>
                  {p.type}
                </span>
                <span style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{p.time}</span>
                <span style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.location}</span>
              </div>
            ))}
          </div>

          {/* Regularization button */}
          <button
            onClick={() => setShowRegularize(true)}
            style={{ width: "100%", height: 34, borderRadius: 6, border: "1px solid var(--outline-v)", background: "transparent", color: "var(--on-variant)", fontSize: 12, fontWeight: 500, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6, transition: "all 0.15s" }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--warn)"; (e.currentTarget as HTMLButtonElement).style.color = "var(--warn)"; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--outline-v)"; (e.currentTarget as HTMLButtonElement).style.color = "var(--on-variant)"; }}
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
