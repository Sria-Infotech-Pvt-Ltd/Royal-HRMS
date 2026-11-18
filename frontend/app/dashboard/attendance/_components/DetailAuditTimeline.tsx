"use client";

// The record's change history as a timeline, newest first: what happened, who did it, when, and the old and new values.

import type { AttendanceAuditEntry } from "@/types/attendance";
import { tint } from "./attendancePalette";
import { auditEventColour, formatEventLabel } from "./detailView";

interface Props {
  entries: AttendanceAuditEntry[];
  loading: boolean;
  error: string | null;
}

export default function DetailAuditTimeline({ entries, loading, error }: Props) {
  if (loading) return <p style={{ fontSize: 13, color: "var(--on-variant)" }}>Loading history…</p>;
  if (error) return <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error}</div>;
  if (entries.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "26px 12px", color: "var(--on-variant)" }}>
        <i className="ti ti-history" aria-hidden="true" style={{ fontSize: 30, color: "var(--outline)" }} />
        <div style={{ fontSize: 13, marginTop: 6 }}>No history for this record yet.</div>
      </div>
    );
  }
  return (
    <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {entries.map((entry, index) => {
        const colour = auditEventColour(entry.event);
        return (
          <li key={index} style={{ display: "flex", gap: 12 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 14 }}>
              <span aria-hidden="true" style={{ width: 12, height: 12, borderRadius: "50%", background: colour, boxShadow: `0 0 0 4px ${tint(colour, 0.18)}`, marginTop: 4, flexShrink: 0 }} />
              {index < entries.length - 1 && <span aria-hidden="true" style={{ flex: 1, width: 2, background: "var(--outline-v)", marginTop: 6 }} />}
            </div>
            <div style={{ paddingBottom: 18, flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11.5, fontWeight: 700, padding: "2px 10px", borderRadius: 999, background: tint(colour, 0.14), color: colour }}>{formatEventLabel(entry.event)}</span>
                <span style={{ fontSize: 12.5, fontWeight: 600 }}>{entry.performed_by}</span>
              </div>
              <div style={{ fontSize: 11.5, color: "var(--on-variant)", margin: "3px 0" }}>{entry.performed_at}</div>
              <div style={{ fontSize: 12.5 }}>{entry.action}</div>
              {entry.old_value && entry.new_value && (
                <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 3 }}>{entry.old_value} <i className="ti ti-arrow-right" aria-hidden="true" /> <strong style={{ color: "var(--on-bg)" }}>{entry.new_value}</strong></div>
              )}
              {entry.remarks && <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 3, fontStyle: "italic" }}>&ldquo;{entry.remarks}&rdquo;</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
