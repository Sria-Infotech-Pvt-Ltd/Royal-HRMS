"use client";

import { useState } from "react";
import { useT } from "@/hooks/useI18n";

export type EmailLogEntry = {
  id:                     string;
  recipient_email:        string;
  subject:                string;
  status:                 "sent" | "failed";
  module:                 string;
  template_name:          string;
  triggered_by_name:      string;
  smtp_settings_name:     string;
  is_resend:              boolean;
  had_attachments:        boolean;
  has_sensitive_context:  boolean;
  /** Why Resend is not offered (a one-time link must be re-issued by the action that made it), or null when a replay is fine. */
  resend_blocked_reason:  string | null;
  error_message:          string;
  created_at:             string;
};

interface Props {
  row: EmailLogEntry;
  moduleClass: string;
  sentAt: string;
  canResend: boolean;
  isResending: boolean;
  onResend: (row: EmailLogEntry) => void;
}

/** One sent (or failed) email as a table row; clicking it opens the delivery details, including why a send failed. */
export default function EmailLogRow({ row, moduleClass, sentAt, canResend, isResending, onResend }: Props) {
  const t = useT();
  const [isOpen, setIsOpen] = useState(false);
  const isFailed = row.status === "failed";
  const tone = isFailed ? "failed" : "sent";
  const isInvite = row.template_name === "onboarding_invite";

  return (
    <>
      <tr
        className={`el-row${isOpen ? " is-open" : ""}${isFailed ? " is-failed" : ""}`}
        onClick={() => setIsOpen(open => !open)}
        onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setIsOpen(open => !open); } }}
        tabIndex={0}
        aria-expanded={isOpen}
      >
        <td>
          <div className={`el-person el-tone-${tone}`}>
            <span className="el-avatar"><i className={`ti ${isFailed ? "ti-mail-exclamation" : "ti-mail-check"}`} /></span>
            <span className="el-to">{row.recipient_email}</span>
          </div>
        </td>
        <td className="el-subject">{row.subject || "—"}</td>
        <td className="el-hide-md">
          <span className={`badge ${moduleClass}`} style={{ textTransform: "capitalize" }}>{row.module || "—"}</span>
        </td>
        <td className="el-hide-md">{row.template_name ? <span className="el-template">{row.template_name}</span> : "—"}</td>
        <td>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span className={`badge ${isFailed ? "badge-error" : "badge-success"}`}>{isFailed ? t("Failed") : t("Sent")}</span>
            {row.is_resend && <span className="badge badge-neutral" style={{ fontSize: 10 }}>{t("Resend")}</span>}
          </div>
        </td>
        <td className="el-hide-md">{row.triggered_by_name || "—"}</td>
        <td style={{ fontSize: 12, color: "var(--on-variant)", whiteSpace: "nowrap" }}>{sentAt}</td>
        <td onClick={event => event.stopPropagation()}>
          {/* On every row, sent or failed. A password reset or other one-time-link email cannot be replayed, so it says where to re-issue
              it; an onboarding invitation is re-issued with a fresh link. Without the permission the button is shown but switched off. */}
          {row.resend_blocked_reason ? (
            <span title={row.resend_blocked_reason} style={{ fontSize: 11, color: "var(--on-variant)", cursor: "help" }}>
              <i className="ti ti-info-circle" /> {t("Re-issue from the employee")}
            </span>
          ) : (
            <button
              className="btn btn-filled btn-sm" style={{ fontSize: ".78rem" }} onClick={() => onResend(row)} disabled={!canResend || isResending} suppressHydrationWarning
              aria-label={t("Resend to {email}", { email: row.recipient_email })}
              title={!canResend ? t("You need permission to resend emails.") : isInvite ? t("Send this person a fresh invitation link") : t("Send this email again")}
            >
              {isResending ? <><i className="ti ti-loader-2 animate-spin" /> {t("Resending…")}</> : <><i className="ti ti-repeat" /> {isInvite ? t("Resend invite") : t("Resend")}</>}
            </button>
          )}
        </td>
      </tr>
      {isOpen && (
        <tr className="el-detail">
          <td colSpan={8}>
            {isFailed && <div className="el-error" role="alert"><b>{t("Why it failed:")}</b> {row.error_message || t("The mail server did not give a reason.")}</div>}
            <dl className="el-detail-grid">
              <div><dt>{t("Sent at")}</dt><dd>{sentAt}</dd></div>
              <div><dt>{t("Mail account used")}</dt><dd>{row.smtp_settings_name || "—"}</dd></div>
              <div><dt>{t("Attachments")}</dt><dd>{row.had_attachments ? t("Yes") : t("None")}</dd></div>
              <div><dt>{t("Sensitive content")}</dt><dd>{row.has_sensitive_context ? t("Yes") : t("No")}</dd></div>
              <div><dt>{t("Template")}</dt><dd>{row.template_name || "—"}</dd></div>
              <div><dt>{t("Triggered by")}</dt><dd>{row.triggered_by_name || t("System")}</dd></div>
            </dl>
          </td>
        </tr>
      )}
    </>
  );
}
