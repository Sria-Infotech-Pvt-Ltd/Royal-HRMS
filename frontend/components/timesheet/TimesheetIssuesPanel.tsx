"use client";

// The server's problems (they block a submit) and warnings (they never do), listed in plain words under the grid.

import type { TimesheetWarning } from "@/types/timesheet";

interface Props {
  errors: string[];
  warnings: TimesheetWarning[];
}

export default function TimesheetIssuesPanel({ errors, warnings }: Props) {
  if (errors.length === 0 && warnings.length === 0) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
      {errors.length > 0 && (
        <div role="alert" style={{ border: "1px solid var(--crit)", borderRadius: 10, padding: "10px 14px", background: "var(--crit-bg, rgba(220,38,38,0.06))" }}>
          <div style={{ fontWeight: 700, fontSize: 12.5, color: "var(--crit)", marginBottom: 4 }}>Please fix these before submitting</div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: "var(--ink)" }}>
            {errors.map(message => <li key={message}>{message}</li>)}
          </ul>
        </div>
      )}
      {warnings.length > 0 && (
        <div role="status" style={{ border: "1px solid var(--warn)", borderRadius: 10, padding: "10px 14px", background: "var(--warn-bg, rgba(217,119,6,0.07))" }}>
          <div style={{ fontWeight: 700, fontSize: 12.5, color: "var(--warn)", marginBottom: 4 }}>Worth a look (you can still submit)</div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: "var(--ink)" }}>
            {warnings.map(warning => <li key={`${warning.code}-${warning.date}`}>{warning.message}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
