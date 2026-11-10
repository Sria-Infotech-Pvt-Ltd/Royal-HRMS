"use client";

import { JOB_STATUS_LABEL, canCancelJob, canRetryEmails, describeEmails, describeJob, emailsInFlight, hasRowErrors } from "@/lib/employeeImport";
import type { ImportJobProgress } from "@/types/employeeImport";

interface Tile { label: string; value: number; color: string }

function TileRow({ tiles, testId }: { tiles: Tile[]; testId: string }) {
  return (
    <div data-testid={testId} style={{ display: "grid", gridTemplateColumns: `repeat(${tiles.length}, 1fr)`, gap: 8, marginBottom: 10 }}>
      {tiles.map(tile => (
        <div key={tile.label} style={{ border: "1px solid var(--outline-v)", borderRadius: 8, padding: "10px 6px", textAlign: "center" }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: tile.color }}>{tile.value}</div>
          <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{tile.label}</div>
        </div>
      ))}
    </div>
  );
}

const SECTION_TITLE = { fontSize: 12, fontWeight: 700, margin: "14px 0 6px" } as const;
const NOTE = { fontSize: 12, color: "var(--on-variant)", lineHeight: 1.6 } as const;
const MAX_FAILURES_SHOWN = 20;

interface Props {
  job: ImportJobProgress;
  isActing: boolean;
  onCancel: () => void;
  onRetryEmails: () => void;
  onDownloadErrors: () => void;
}

/**
 * Progress of one background import. Two separate sections on purpose: CREATING the employees (the import itself) and DELIVERING
 * the activation emails (a different, slower step that can fail on its own without affecting the employees).
 */
export default function ImportJobPanel({ job, isActing, onCancel, onRetryEmails, onDownloadErrors }: Props) {
  const { invitations } = job;
  const failures = job.invitation_failures;
  return (
    <div data-testid="import-job-panel">
      <div className="alert" style={{ marginBottom: 12 }}>
        <i className={`ti ${job.is_active ? "ti-loader-2 spin" : job.status === "completed" ? "ti-circle-check" : "ti-info-circle"}`} />
        <span data-testid="job-headline"><strong>{JOB_STATUS_LABEL[job.status]}.</strong> {describeJob(job)}</span>
      </div>

      <div style={{ height: 8, borderRadius: 4, background: "var(--outline-v)", overflow: "hidden", marginBottom: 12 }} aria-label="Import progress">
        <div style={{ width: `${job.percent}%`, height: "100%", background: "var(--primary)", transition: "width 0.4s" }} />
      </div>

      <div style={SECTION_TITLE}>1. Creating employees</div>
      <TileRow testId="employee-tiles" tiles={[
        { label: "Total rows", value: job.total_rows, color: "var(--on-bg)" },
        { label: "Processed", value: job.processed_rows, color: "var(--on-bg)" },
        { label: "Employees created", value: job.created, color: "var(--success)" },
        { label: "Rows failed", value: job.failed_rows, color: job.failed_rows > 0 ? "var(--error)" : "var(--on-variant)" },
      ]} />

      <div style={SECTION_TITLE}>2. Activation emails</div>
      <TileRow testId="email-tiles" tiles={[
        { label: "Waiting", value: emailsInFlight(job), color: "var(--warn)" },
        { label: "Sent", value: invitations.sent, color: "var(--success)" },
        { label: "Failed", value: invitations.failed, color: invitations.failed > 0 ? "var(--error)" : "var(--on-variant)" },
      ]} />
      <div data-testid="email-headline" style={NOTE}>{describeEmails(job)}</div>
      <div style={{ ...NOTE, fontSize: 11 }}>
        “Sent” means the mail server accepted the email. It does not prove the employee&apos;s inbox received it.
      </div>

      {failures.length > 0 && (
        <div style={{ border: "1px solid var(--outline-v)", borderRadius: 8, padding: 10, marginTop: 10 }}>
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>Emails not sent (the employees were created)</div>
          {failures.slice(0, MAX_FAILURES_SHOWN).map(failure => (
            <div key={`${failure.row}-${failure.employee_id}`} style={NOTE}>Row {failure.row}: employee {failure.employee_id}: {failure.reason}</div>
          ))}
          {failures.length > MAX_FAILURES_SHOWN && <div style={NOTE}>…and {failures.length - MAX_FAILURES_SHOWN} more.</div>}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
        {canRetryEmails(job) && (
          <button className="btn btn-filled btn-sm" onClick={onRetryEmails} disabled={isActing} suppressHydrationWarning>
            <i className="ti ti-refresh" /> Retry {invitations.failed} failed email{invitations.failed === 1 ? "" : "s"}
          </button>
        )}
        {hasRowErrors(job) && (
          <button className="btn btn-ghost btn-sm" onClick={onDownloadErrors} suppressHydrationWarning>
            <i className="ti ti-download" /> Download error report (Excel)
          </button>
        )}
        {canCancelJob(job) && (
          <button className="btn btn-ghost btn-sm" onClick={onCancel} disabled={isActing} suppressHydrationWarning>
            <i className="ti ti-player-stop" /> Cancel import
          </button>
        )}
      </div>
      {canCancelJob(job) && (
        <div style={{ ...NOTE, marginTop: 6 }}>Cancelling stops after the current batch. Employees already created stay.</div>
      )}
    </div>
  );
}
