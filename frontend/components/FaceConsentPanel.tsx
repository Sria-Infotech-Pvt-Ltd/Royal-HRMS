"use client";

// Shown before the camera opens in any face-capture flow (self-service
// FaceRegistrationModal and HR-witnessed HRFaceCaptureModal) — consent must
// be obtained before biometric data collection starts, not just before
// submission. Requires an explicit checkbox tick; there is no "just close
// this and continue" shortcut.
import { useState } from "react";

interface FaceConsentPanelProps {
  noticeText: string;
  onAcknowledge: () => void;
  onCancel: () => void;
}

export default function FaceConsentPanel({ noticeText, onAcknowledge, onCancel }: FaceConsentPanelProps) {
  const [checked, setChecked] = useState(false);

  return (
    <div className="flex flex-col py-2 px-1">
      <div className="flex items-start gap-3 mb-4">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
          style={{ background: "rgba(124,58,237,0.08)" }}
        >
          <i className="ti ti-shield-lock" style={{ fontSize: 18, color: "var(--primary)" }} />
        </div>
        <div>
          <h3 className="text-base font-bold mb-1" style={{ color: "var(--on-bg)" }}>
            Biometric data consent
          </h3>
          <p className="text-sm leading-relaxed" style={{ color: "var(--on-variant)" }}>
            {noticeText}
          </p>
        </div>
      </div>

      <label
        className="flex items-start gap-2.5 mb-5 p-3 rounded-lg cursor-pointer"
        style={{ background: "var(--bg-low)", border: "1px solid var(--outline-v)" }}
      >
        <input
          type="checkbox"
          checked={checked}
          onChange={e => setChecked(e.target.checked)}
          suppressHydrationWarning
          className="mt-0.5"
        />
        <span className="text-sm" style={{ color: "var(--on-bg)" }}>
          I have read and agree to the above.
        </span>
      </label>

      <div className="flex justify-end gap-3">
        <button className="btn btn-ghost btn-sm" suppressHydrationWarning onClick={onCancel} type="button">
          Cancel
        </button>
        <button
          className="btn btn-primary btn-sm"
          suppressHydrationWarning
          disabled={!checked}
          onClick={onAcknowledge}
          type="button"
        >
          I Agree &amp; Continue
        </button>
      </div>
    </div>
  );
}
