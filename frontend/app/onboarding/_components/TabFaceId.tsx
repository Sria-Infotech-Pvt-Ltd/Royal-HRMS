"use client";

import type { FaceRegistrationRequest } from "@/types/faceRegistration";

// ── Tab: Face ID ──────────────────────────────────────────────────────────────
// Only rendered when the admin's org-wide Face ID Verification toggle
// (Attendance Settings) is mandatory. Capture goes through the same
// FaceRegistrationModal/useFaceRegistrationCapture flow used on the Profile
// page; "registered" here just means submitted — HR approval happens
// afterwards, but submission is already unblocked at that point (canSubmit
// above only checks that a registration exists, not its approval status).
// Pure/prop-driven — shared by the self-service onboarding wizard and the
// HR-completes-onboarding wizard.

export default function TabFaceId({
  registration, onRegister,
}: {
  registration: Partial<FaceRegistrationRequest> | null;
  onRegister: () => void;
}) {
  const status = registration?.status;

  return (
    <div>
      <p style={{ color: "var(--on-variant)", marginBottom: "1.25rem", fontSize: ".9rem", lineHeight: 1.6 }}>
        Your organisation requires a registered face ID for web clock-in/out. Register once here —
        we run a quick liveness check to confirm it&apos;s really you, then send it to HR for approval.
        You won&apos;t be able to submit your onboarding profile until this step is complete.
      </p>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem",
        padding: "1rem 1.25rem", borderRadius: 12,
        border: `1.5px solid ${status ? "var(--success)" : "var(--outline-v)"}`,
        background: status ? "var(--success-c)" : "#fff",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 9, background: status ? "var(--success)" : "var(--bg-high)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <i className="ti ti-face-id" style={{ color: status ? "#fff" : "var(--on-variant)", fontSize: 18 }} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: ".9rem", color: "var(--on-bg)" }}>
              {status === "approved" && "Face ID approved"}
              {status === "pending" && "Face ID submitted — pending HR approval"}
              {status === "rejected" && "Face ID rejected — please register again"}
              {!status && "Face ID not yet registered"}
            </div>
          </div>
        </div>
        {status === "pending" ? (
          // No re-submit affordance while a request is already awaiting HR
          // review — matches the self-service Profile page's rule for the
          // same state. Without this, repeatedly clicking through here
          // (most likely exactly what happens during onboarding, while
          // waiting on HR) creates duplicate pending requests; the backend
          // now also rejects a second one outright, but hiding the button
          // is the actual fix for the confusing "why did clicking do
          // nothing" experience that would otherwise cause.
          <span style={{ fontSize: ".83rem", color: "var(--on-variant)", fontWeight: 600 }}>
            Awaiting review
          </span>
        ) : (
          <button
            className="btn btn-ghost"
            style={{ fontSize: ".83rem", borderColor: status ? "var(--success)" : undefined, color: status ? "var(--success)" : undefined }}
            onClick={onRegister}
            type="button"
          >
            {status === "approved" ? "Update" : status ? "Register Again" : "Register Face ID"}
          </button>
        )}
      </div>
    </div>
  );
}
