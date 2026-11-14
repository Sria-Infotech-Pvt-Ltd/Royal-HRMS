"use client";

// The editable week: holds what the person has typed, and offers Save draft / Submit (Resubmit after a send-back).
// The parent re-creates this component (by key) whenever the server hands back a new version of the sheet, so the grid
// always starts from what is saved. The server remains the judge of every rule; this only blocks hours that are not
// quarter-hour numbers, so a typo never reaches it.

import { useMemo, useState } from "react";
import TimesheetProjects from "@/components/timesheet/TimesheetProjects";
import TimesheetHistory from "@/components/timesheet/TimesheetHistory";
import TimesheetIssuesPanel from "@/components/timesheet/TimesheetIssuesPanel";
import { billableTotal, formatHours, hasInvalidCells, isDirty, toGridLines, toSavePayload, weekTotal } from "@/lib/timesheet";
import type { GridLine, TimesheetSavePayload, TimesheetWeekView } from "@/types/timesheet";

interface Props {
  view: TimesheetWeekView;
  /** Looking at someone else's workspace: show the sheet but allow no changes at all. */
  isReadOnly?: boolean;
  isSaving: boolean;
  isSubmitting: boolean;
  problems: string[];
  onSave: (payload: TimesheetSavePayload) => Promise<boolean>;
  onSubmit: () => Promise<boolean>;
}

function Banner({ tone, children }: { tone: "crit" | "warn" | "ok"; children: React.ReactNode }) {
  return (
    <div role="status" style={{ border: `1px solid var(--${tone})`, borderRadius: 10, padding: "10px 14px", margin: "12px 0", fontSize: 12.5, color: "var(--ink)" }}>
      {children}
    </div>
  );
}

function StatusBanner({ view }: { view: TimesheetWeekView }) {
  if (view.status === "returned" && view.return_reason) {
    return <Banner tone="crit"><b>Sent back for changes:</b> {view.return_reason}. Fix the hours and resubmit.</Banner>;
  }
  if (view.status === "submitted") return <Banner tone="warn">Waiting for approval{view.approver ? ` from ${view.approver.name}` : ""}. You cannot edit it meanwhile.</Banner>;
  if (view.status === "approved") return <Banner tone="ok">Approved{view.decided_by ? ` by ${view.decided_by.name}` : ""}. This timesheet is locked.</Banner>;
  return null;
}

export default function TimesheetEditor({ view, isReadOnly: isViewOnly = false, isSaving, isSubmitting, problems, onSave, onSubmit }: Props) {
  const savedLines = useMemo(() => toGridLines(view.lines), [view.lines]);
  const [lines, setLines] = useState<GridLine[]>(savedLines);
  const dates = view.days.map(day => day.date);
  const isReadOnly = isViewOnly || !view.is_editable;
  const isBusy = isSaving || isSubmitting;
  const hasTypo = hasInvalidCells(lines);
  const isChanged = isDirty(lines, savedLines);
  const total = weekTotal(lines, dates);
  const billable = billableTotal(lines, dates);

  function update(lineKey: string, change: (line: GridLine) => GridLine) {
    setLines(previous => previous.map(line => (line.key === lineKey ? change(line) : line)));
  }

  async function handleSubmit() {
    if (isChanged && !(await onSave(toSavePayload(lines)))) return;
    await onSubmit();
  }

  return (
    <div>
      <StatusBanner view={view} />
      <TimesheetProjects
        days={view.days} lines={lines} limits={view.limits} isReadOnly={isReadOnly}
        onHoursChange={(key, date, hours) => update(key, line => ({ ...line, cells: { ...line.cells, [date]: { note: line.cells[date]?.note ?? "", hours } } }))}
        onNoteChange={(key, date, note) => update(key, line => ({ ...line, cells: { ...line.cells, [date]: { hours: line.cells[date]?.hours ?? "", note } } }))}
        onBillableChange={(key, isBillable) => update(key, line => ({ ...line, is_billable: isBillable }))}
      />
      <p style={{ fontSize: 12.5, color: "var(--muted)", margin: "10px 2px" }}>
        Week total <b style={{ color: "var(--ink)" }}>{formatHours(total)}</b> of {formatHours(Number(view.limits.weekly_target_hours))} target hours (a guide, not a limit)
        {" · "}Billable <b style={{ color: "var(--ink)" }}>{formatHours(billable)}</b> · Non-billable <b style={{ color: "var(--ink)" }}>{formatHours(total - billable)}</b>
      </p>
      {hasTypo && <p role="alert" style={{ color: "var(--crit)", fontSize: 12.5, margin: "0 2px 8px" }}>Some hours are not valid. Use whole or quarter hours from 0 to 24 (for example 7.5).</p>}
      <TimesheetIssuesPanel errors={problems.length > 0 ? problems : view.issues?.errors ?? []} warnings={view.issues?.warnings ?? []} />
      {!isReadOnly && (
        <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
          <button type="button" className="rvbtn" disabled={isBusy || hasTypo || !isChanged} onClick={() => onSave(toSavePayload(lines))}>
            {isSaving ? "Saving…" : "Save draft"}
          </button>
          <button type="button" className="rvbtn pri" disabled={isBusy || hasTypo} onClick={handleSubmit}>
            {isSubmitting ? "Submitting…" : view.status === "returned" ? "Resubmit" : "Submit for approval"}
          </button>
        </div>
      )}
      <h3 style={{ fontSize: 13, margin: "22px 0 8px" }}>History</h3>
      <TimesheetHistory events={view.events} />
    </div>
  );
}
