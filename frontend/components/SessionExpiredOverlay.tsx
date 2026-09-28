"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

export default function SessionExpiredOverlay() {
  const router       = useRouter();
  const [visible, setVisible] = useState(false);
  const triggeredRef = useRef(false);   // deduplicates multiple session:expired events
  const timerRef     = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function onExpired() {
      if (triggeredRef.current) return; // already handling — ignore duplicate fires
      triggeredRef.current = true;
      setVisible(true);
      timerRef.current = setTimeout(() => {
        setVisible(false);
        triggeredRef.current = false;
        router.replace("/login");
      }, 2500);
    }

    window.addEventListener("session:expired", onExpired);
    return () => {
      window.removeEventListener("session:expired", onExpired);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [router]);

  if (!visible) return null;

  return (
    <div style={{
      position:       "fixed",
      inset:          0,
      // Must outrank every other in-app overlay (feature modals all use
      // 9999) — this notice fires while some modal may already be open
      // (e.g. mid profile-photo-upload), and if it renders behind that
      // modal the user never sees it: the action just silently fails
      // with no explanation, looking like a plain upload bug instead of
      // "you were logged out".
      zIndex:         2147483647,
      background:     "rgba(10, 18, 32, 0.72)",
      backdropFilter: "blur(4px)",
      display:        "flex",
      alignItems:     "center",
      justifyContent: "center",
    }}>
      <div style={{
        background:   "var(--surface)",
        borderRadius: "var(--radius-lg)",
        padding:      "36px 40px",
        textAlign:    "center",
        maxWidth:     "360px",
        width:        "90%",
        boxShadow:    "var(--shadow-md)",
      }}>
        <div style={{
          width:        "48px",
          height:       "48px",
          borderRadius: "50%",
          border:       "3px solid var(--bg-high)",
          borderTop:    "3px solid var(--primary)",
          animation:    "spin 0.8s linear infinite",
          margin:       "0 auto 20px",
        }} />
        <p style={{ fontSize: "16px", fontWeight: 600, color: "var(--on-bg)", marginBottom: "8px" }}>
          Session Expired
        </p>
        <p style={{ fontSize: "13px", color: "var(--on-variant)", lineHeight: 1.6 }}>
          Your session has timed out. Signing you out…
        </p>
      </div>
    </div>
  );
}
