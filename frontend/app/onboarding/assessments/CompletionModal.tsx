"use client";

import type { CompleteData } from "./_types";

export default function CompletionModal({ result, title, attemptNumber, isLastPending, retaking, onRetake, onContinue, onDashboard }: {
  result: CompleteData; title: string; attemptNumber: number; isLastPending: boolean;
  retaking: boolean; onRetake: () => void; onContinue: () => void; onDashboard: () => void;
}) {
  const pct = result.max_score > 0 ? Math.round((result.score / result.max_score) * 100) : 0;
  const R = 52; const C = 2 * Math.PI * R;
  const passed = result.passed;
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.75)", backdropFilter: "blur(4px)", zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div style={{ background: "var(--surface)", borderRadius: 20, width: "100%", maxWidth: 380, boxShadow: "0 25px 60px rgba(0,0,0,0.25)", overflow: "hidden" }}>
        <div style={{ height: 4, background: passed ? "linear-gradient(90deg,#16a34a,#22c55e)" : "linear-gradient(90deg,#dc2626,#ef4444)" }} />
        <div style={{ padding: "32px 32px 28px", textAlign: "center" }}>
          <div style={{ position: "relative", width: 136, height: 136, margin: "0 auto 20px" }}>
            <svg width="136" height="136" style={{ transform: "rotate(-90deg)" }}>
              <circle cx="68" cy="68" r={R} fill="none" stroke="#f1f5f9" strokeWidth="10" />
              <circle cx="68" cy="68" r={R} fill="none" stroke={passed ? "#16a34a" : "#ef4444"} strokeWidth="10" strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C - (pct / 100) * C} style={{ transition: "stroke-dashoffset 0.8s ease" }} />
            </svg>
            <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: 28, fontWeight: 800, color: "#0f172a", lineHeight: 1 }}>{result.score}</span>
              <span style={{ fontSize: 12, color: "#94a3b8" }}>/ {result.max_score}</span>
            </div>
          </div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, background: passed ? "#dcfce7" : "#fee2e2", borderRadius: 20, padding: "4px 14px", marginBottom: 8 }}>
            <i className={`ti ${passed ? "ti-circle-check" : "ti-circle-x"}`} style={{ color: passed ? "#16a34a" : "#dc2626", fontSize: 14 }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: passed ? "#15803d" : "#dc2626" }}>{passed ? "Passed" : "Not Passed"}</span>
          </div>
          <p style={{ fontSize: 20, fontWeight: 700, color: "#0f172a", margin: "0 0 4px" }}>{pct}% Score</p>
          <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 24px" }}>{title} · Attempt #{attemptNumber}</p>
          {passed && isLastPending ? (
            <button suppressHydrationWarning onClick={onDashboard} style={{ width: "100%", padding: "12px 0", borderRadius: 10, background: "#7c3aed", color: "#fff", fontWeight: 600, fontSize: 14, border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              Go to Dashboard <i className="ti ti-arrow-right" />
            </button>
          ) : passed ? (
            <button suppressHydrationWarning onClick={onContinue} style={{ width: "100%", padding: "12px 0", borderRadius: 10, background: "#7c3aed", color: "#fff", fontWeight: 600, fontSize: 14, border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              Continue to Next Assessment <i className="ti ti-arrow-right" />
            </button>
          ) : (
            <button suppressHydrationWarning onClick={onRetake} disabled={retaking} style={{ width: "100%", padding: "12px 0", borderRadius: 10, background: retaking ? "#94a3b8" : "#dc2626", color: "#fff", fontWeight: 600, fontSize: 14, border: "none", cursor: retaking ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              {retaking ? <><i className="ti ti-loader-2 spin" />Starting…</> : <><i className="ti ti-refresh" />Re-take Assessment</>}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
