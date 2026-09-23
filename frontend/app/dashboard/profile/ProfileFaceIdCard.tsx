"use client";

import type { FaceRegistrationCardState } from "@/hooks/useFaceRegistrationCard";

interface ProfileFaceIdCardProps {
  faceCardState: FaceRegistrationCardState;
  faceRejectionNotes: string;
  onRegister: () => void;
}

export default function ProfileFaceIdCard({ faceCardState, faceRejectionNotes, onRegister }: ProfileFaceIdCardProps) {
  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-face-id" />Face Registration</span>
      </div>
      <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px" }}>
        <i className="ti ti-face-id" style={{ fontSize: 22, color: "var(--on-variant)" }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          {faceCardState === "approved" && (
            <>
              <div style={{ fontSize: 13, color: "var(--success)" }}>
                <i className="ti ti-circle-check" style={{ marginRight: 4 }} />Face ID registered
              </div>
              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Required for web clock-in/out — already verified.</div>
            </>
          )}
          {faceCardState === "pending" && (
            <>
              <div style={{ fontSize: 13, color: "var(--on-bg)" }}>Face ID pending HR approval</div>
              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>You&apos;ll be able to clock in with it once it&apos;s approved.</div>
            </>
          )}
          {faceCardState === "rejected" && (
            <>
              <div style={{ fontSize: 13, color: "var(--error)" }}>Face ID registration was rejected</div>
              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{faceRejectionNotes || "Please update and resubmit."}</div>
            </>
          )}
          {faceCardState === "not_registered" && (
            <>
              <div style={{ fontSize: 13, color: "var(--on-bg)" }}>Face ID not yet registered</div>
              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                Usually done during onboarding — register it below if you missed that step.
              </div>
            </>
          )}
        </div>
        {(faceCardState === "approved" || faceCardState === "rejected") && (
          <button type="button" className="btn btn-primary btn-sm" suppressHydrationWarning onClick={onRegister}>
            <i className="ti ti-camera" /> Update My Face
          </button>
        )}
        {faceCardState === "not_registered" && (
          <button type="button" className="btn btn-primary btn-sm" suppressHydrationWarning onClick={onRegister}>
            <i className="ti ti-camera" /> Register My Face
          </button>
        )}
      </div>
    </div>
  );
}
