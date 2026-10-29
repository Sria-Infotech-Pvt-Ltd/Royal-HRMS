"use client";

// What happened since HR started this person's onboarding, the current state in plain words, and the resend action.

import { useState } from "react";
import Modal from "@/components/Modal";
import { useOnboardingHistory } from "@/hooks/useOnboardingHistory";
import { formatDateTime } from "@/lib/formatDate";
import type { OnboardingEventType, OnboardingStateCode } from "@/types/onboardingHistory";

interface Props {
  employeeUuid: string;
  employeeName: string;
  onClose: () => void;
  /** Called after a resend so the directory row can refresh. */
  onChanged: () => void;
}

const EVENT_ICON: Record<OnboardingEventType, string> = {
  initiated: "ti-user-plus", email_sent: "ti-mail-check", email_failed: "ti-mail-exclamation", email_resent: "ti-mail-forward",
  email_corrected: "ti-edit", link_opened: "ti-link", first_login: "ti-login", password_set: "ti-key", activated: "ti-circle-check",
};

const EVENT_COLOR: Partial<Record<OnboardingEventType, string>> = {
  email_failed: "var(--crit, #dc2626)", activated: "var(--ok, #16a34a)",
};

const STATE_TONE: Record<OnboardingStateCode, { bg: string; ink: string }> = {
  active: { bg: "var(--ok-bg, #dcfce7)", ink: "var(--ok, #166534)" },
  email_failed: { bg: "var(--crit-bg, #fee2e2)", ink: "var(--crit, #991b1b)" },
  link_expired: { bg: "var(--crit-bg, #fee2e2)", ink: "var(--crit, #991b1b)" },
  awaiting_login: { bg: "var(--amber-bg, #fef3c7)", ink: "var(--amber-ink, #92400e)" },
  link_opened: { bg: "var(--amber-bg, #fef3c7)", ink: "var(--amber-ink, #92400e)" },
  not_logged_in: { bg: "var(--amber-bg, #fef3c7)", ink: "var(--amber-ink, #92400e)" },
};

export default function OnboardingHistoryModal({ employeeUuid, employeeName, onClose, onChanged }: Props) {
  const { history, loading, error, resend, isResending, resendError } = useOnboardingHistory(employeeUuid, onChanged);
  const [isCorrecting, setIsCorrecting] = useState(false);
  const [correctedEmail, setCorrectedEmail] = useState("");

  async function onResend() {
    const succeeded = await resend(isCorrecting && correctedEmail.trim() ? correctedEmail.trim() : undefined);
    if (succeeded) { setIsCorrecting(false); setCorrectedEmail(""); }
  }

  const state = history?.state;
  const tone = state ? STATE_TONE[state.code] : null;
  const timeline = history?.timeline ?? [];

  return (
    <Modal
      title={<div className="text-[18px] font-bold">Onboarding · <span style={{ color: "var(--primary)", fontStyle: "italic" }}>{employeeName}</span></div>}
      onClose={onClose}
      closeDisabled={isResending}
      footer={<button className="rvbtn ghost" onClick={onClose} disabled={isResending}>Close</button>}
    >
      {loading && <div style={{ color: "var(--muted)" }}>Loading onboarding history…</div>}
      {error && !loading && <div role="alert" style={{ color: "var(--crit, #dc2626)" }}>{error}</div>}

      {history && state && tone && (
        <div style={{ display: "grid", gap: 16 }}>
          <div role="status" style={{ background: tone.bg, color: tone.ink, padding: "10px 12px", borderRadius: 8, fontWeight: 600 }}>
            {state.message}
          </div>

          <div style={{ fontSize: 13, color: "var(--muted)" }}>
            Invite goes to <strong style={{ color: "var(--ink)" }}>{history.email}</strong>
            {history.invite_expires_at && history.state.code !== "active" && <> · link valid until {formatDateTime(history.invite_expires_at)}</>}
          </div>

          {state.can_resend && (
            <div style={{ display: "grid", gap: 8 }}>
              {isCorrecting && (
                <label style={{ display: "grid", gap: 4, fontSize: 13 }}>
                  Correct email address
                  <input
                    type="email" value={correctedEmail} onChange={event => setCorrectedEmail(event.target.value)}
                    placeholder="name@company.com" autoComplete="off" className="rvinput"
                  />
                </label>
              )}
              {resendError && <div role="alert" style={{ color: "var(--crit, #dc2626)", fontSize: 13 }}>{resendError}</div>}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="rvbtn pri" onClick={onResend} disabled={isResending || (isCorrecting && !correctedEmail.trim())}>
                  {isResending ? "Sending…" : "Resend Onboarding Email"}
                </button>
                <button className="rvbtn ghost" onClick={() => { setIsCorrecting(value => !value); setCorrectedEmail(""); }} disabled={isResending}>
                  {isCorrecting ? "Keep current address" : "Correct email address"}
                </button>
              </div>
              <div style={{ fontSize: 12, color: "var(--muted)" }}>Up to {history.resend_limit_per_hour} resends per hour. Sending again makes the previous link stop working.</div>
            </div>
          )}

          <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 12 }} aria-label="Onboarding timeline">
            {timeline.map(item => (
              <li key={item.id} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                <i className={`ti ${EVENT_ICON[item.event]}`} aria-hidden="true" style={{ fontSize: 18, color: EVENT_COLOR[item.event] ?? "var(--muted)", marginTop: 2 }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, color: EVENT_COLOR[item.event] }}>
                    {item.label}{item.actor_name && <span style={{ fontWeight: 400, color: "var(--muted)" }}> · by {item.actor_name}</span>}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>{formatDateTime(item.at)}</div>
                  {item.detail && <div style={{ fontSize: 13, marginTop: 2, overflowWrap: "anywhere" }}>{item.detail}</div>}
                </div>
              </li>
            ))}
            {timeline.length === 0 && <li style={{ color: "var(--muted)" }}>No onboarding events recorded for this employee.</li>}
          </ol>
        </div>
      )}
    </Modal>
  );
}
