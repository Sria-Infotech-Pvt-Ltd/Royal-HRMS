"use client";

import { useState } from "react";
import { useClockWidget } from "@/hooks/useClockWidget";
import CorrectionModal from "@/app/dashboard/my-attendance/_components/CorrectionModal";

function todayString() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function ClockInButton() {
  const { session, isLoading, isPunching, punch } = useClockWidget();
  const [showModal, setShowModal] = useState(false);

  const isClockedIn = session?.is_clocked_in ?? false;
  const isBusy      = isLoading || isPunching;

  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
        <button
          onClick={() => punch(isClockedIn ? "OUT" : "IN")}
          disabled={isBusy}
          style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "10px 24px", borderRadius: 28, border: "none",
            cursor: isBusy ? "not-allowed" : "pointer",
            fontSize: 14, fontWeight: 700,
            background: "#ffffff",
            color: isClockedIn ? "#dc2626" : "#16a34a",
            opacity: isBusy ? 0.7 : 1,
            boxShadow: isClockedIn ? "0 4px 16px rgba(220,38,38,0.25)" : "0 4px 16px rgba(22,163,74,0.25)",
            transition: "box-shadow 0.15s, transform 0.1s, opacity 0.15s",
            letterSpacing: "0.01em", whiteSpace: "nowrap",
          }}
          onMouseEnter={e => { if (!isBusy) (e.currentTarget as HTMLButtonElement).style.transform = "translateY(-1px)"; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.transform = "translateY(0)"; }}
        >
          {isPunching ? (
            <>
              <i className="ti ti-loader-2" style={{ fontSize: 15, animation: "spin 1s linear infinite" }} />
              Please wait…
            </>
          ) : (
            <>
              <span style={{
                width: 9, height: 9, borderRadius: "50%",
                background: isClockedIn ? "#dc2626" : "#16a34a",
                display: "inline-block", flexShrink: 0,
                animation: !isClockedIn ? "clockPulse 2s ease-in-out infinite" : "none",
              }} />
              <i className={`ti ${isClockedIn ? "ti-clock-out" : "ti-clock-in"}`} style={{ fontSize: 15 }} />
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
    </>
  );
}
