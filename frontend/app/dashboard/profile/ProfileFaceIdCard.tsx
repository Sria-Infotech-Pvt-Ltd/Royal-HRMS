"use client";

import type { FaceRegistrationCardState } from "@/hooks/useFaceRegistrationCard";
import { useT } from "@/hooks/useI18n";

interface ProfileFaceIdCardProps {
  faceCardState: FaceRegistrationCardState;
  /** The server's one instruction for this person under the organisation's Face ID mode. */
  message: string;
  /** Employees may register their own Face ID in this organisation (it is not HR-in-person only). */
  canSelfRegister: boolean;
  faceRejectionNotes: string;
  onRegister: () => void;
}

const HEADLINES: Record<Exclude<FaceRegistrationCardState, "disabled">, string> = {
  approved: "Face ID registered",
  pending: "Face ID waiting for approval",
  rejected: "Face ID registration was rejected",
  not_registered: "Face ID not yet registered",
};

export default function ProfileFaceIdCard({ faceCardState, message, canSelfRegister, faceRejectionNotes, onRegister }: ProfileFaceIdCardProps) {
  const t = useT();
  if (faceCardState === "disabled") return null;
  const color = faceCardState === "approved" ? "var(--success)" : faceCardState === "rejected" ? "var(--error)" : "var(--on-bg)";
  const canAct = canSelfRegister && faceCardState !== "pending";

  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-face-id" />{t("Face Registration")}</span>
      </div>
      <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px" }}>
        <i className="ti ti-face-id" style={{ fontSize: 22, color: "var(--on-variant)" }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, color }}>{t(HEADLINES[faceCardState])}</div>
          <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
            {message}
            {faceCardState === "rejected" && faceRejectionNotes ? ` ${t("Reason: {notes}", { notes: faceRejectionNotes })}` : ""}
          </div>
        </div>
        {canAct && (
          <button type="button" className="btn btn-primary btn-sm" suppressHydrationWarning onClick={onRegister}>
            <i className="ti ti-camera" /> {faceCardState === "approved" || faceCardState === "rejected" ? t("Update My Face") : t("Register My Face")}
          </button>
        )}
      </div>
    </div>
  );
}
