"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { formatDate } from "@/lib/formatDate";
import type { BirthdayEmployee } from "@/types/employeeDashboard";

function initials(name: string): string {
  return name.split(" ").filter(Boolean).slice(0, 2).map(w => w[0]?.toUpperCase() ?? "").join("");
}

interface Props {
  employee: BirthdayEmployee;
  onClose:  () => void;
}

/**
 * Feature 3/4 — the "larger" celebration popup opened by clicking a birthday
 * announcement. Fires a one-time confetti burst (canvas-confetti — the only
 * animation dependency in the project, chosen for its near-zero footprint
 * and imperative "fire once" API, so it never loops or re-triggers on rerender).
 */
export default function BirthdayCelebrationModal({ employee, onClose }: Props) {
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return; // guards against React StrictMode's dev double-invoke
    fired.current = true;
    let cancelled = false;
    import("canvas-confetti").then(({ default: confetti }) => {
      if (cancelled) return;
      confetti({ particleCount: 120, spread: 90, origin: { y: 0.5 }, colors: ["#db2777", "#9333ea", "#f59e0b", "#10b981"] });
      setTimeout(() => {
        if (!cancelled) confetti({ particleCount: 60, spread: 120, origin: { y: 0.4 } });
      }, 300);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const today = formatDate(new Date());

  const overlay = (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 9999, padding: 20,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "var(--surface)", borderRadius: 16, width: "min(420px, 100%)",
          padding: "32px 28px", textAlign: "center", position: "relative",
          boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
        }}
      >
        <button
          onClick={onClose}
          aria-label="Close"
          suppressHydrationWarning
          style={{ position: "absolute", top: 14, right: 14, background: "none", border: "none", cursor: "pointer", color: "var(--on-variant)", fontSize: 18 }}
        >
          <i className="ti ti-x" />
        </button>

        <div style={{ fontSize: 36, marginBottom: 6 }}>🎉🎂🎈</div>

        {/* Employee photo — no avatar/photo field exists in this system yet, so this
            initials avatar (same convention used across every other dashboard widget)
            is the photo placeholder. */}
        <div style={{
          width: 84, height: 84, borderRadius: "50%", margin: "0 auto 14px",
          background: "linear-gradient(135deg, #db2777, #9333ea)", color: "#fff",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 28, fontWeight: 700,
        }}>
          {initials(employee.full_name)}
        </div>

        <div style={{ fontSize: 20, fontWeight: 800, color: "var(--on-bg)" }}>
          Happy Birthday, {employee.full_name}!
        </div>
        <div style={{ fontSize: 13, color: "var(--on-variant)", marginTop: 4 }}>
          {employee.designation}{employee.department ? ` · ${employee.department}` : ""}
        </div>

        <div style={{
          marginTop: 18, padding: "14px 16px", borderRadius: 10,
          background: "rgba(219,39,119,0.06)", fontSize: 13, color: "var(--on-bg)", lineHeight: 1.6,
        }}>
          {employee.message || "Wishing you a wonderful year ahead!"}
        </div>

        <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 16 }}>
          {today}
        </div>
      </div>
    </div>
  );

  return createPortal(overlay, document.body ?? document.documentElement);
}
