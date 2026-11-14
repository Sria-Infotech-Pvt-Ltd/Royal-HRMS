"use client";

// One project (or the Internal / Non-project row) as a card: its name, whether it is billable, the week's hours on it, and a
// strip of the days it has hours on. "Edit hours" opens the seven days with an hours box and an optional note each; a read-only
// sheet shows "View days" instead. A day is closed to typing when the person is not employed that day, the day has not happened
// yet, or the sheet is read-only; holidays, weekly offs and leave days stay open (the server only warns about those).

import { useState } from "react";
import { dayChipLabel, dayNumber, formatHours, isValidHoursText, lineTotal } from "@/lib/timesheet";
import type { GridLine, TimesheetDay } from "@/types/timesheet";

interface Props {
  line: GridLine;
  days: TimesheetDay[];
  isReadOnly: boolean;
  maxNoteLength: number;
  onHoursChange: (lineKey: string, date: string, text: string) => void;
  onNoteChange: (lineKey: string, date: string, text: string) => void;
  onBillableChange: (lineKey: string, isBillable: boolean) => void;
}

function isClosed(day: TimesheetDay, isReadOnly: boolean): boolean {
  return isReadOnly || !day.is_employed || day.is_future;
}

function DayRow({ line, day, isReadOnly, maxNoteLength, onHoursChange, onNoteChange }: Omit<Props, "days" | "onBillableChange"> & { day: TimesheetDay }) {
  const cell = line.cells[day.date] ?? { hours: "", note: "" };
  const isInvalid = !isValidHoursText(cell.hours);
  const chip = dayChipLabel(day);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "92px 70px 1fr", gap: 10, alignItems: "center", opacity: day.is_employed ? 1 : 0.55 }}>
      <div style={{ fontSize: 12.5, fontWeight: 600 }}>
        {day.weekday} {dayNumber(day.date)}
        {chip && <div><span className="chip warn" style={{ fontSize: 9.5 }}>{chip}</span></div>}
      </div>
      <input
        value={cell.hours} inputMode="decimal" placeholder="0" disabled={isClosed(day, isReadOnly)} aria-invalid={isInvalid}
        aria-label={`${line.project_name} hours on ${day.date}`} onChange={event => onHoursChange(line.key, day.date, event.target.value)}
        style={{ height: 34, textAlign: "center", borderRadius: 8, fontSize: 13, border: `1px solid ${isInvalid ? "var(--crit)" : "var(--line)"}`, background: "var(--surface)", color: "var(--ink)" }}
      />
      <input
        value={cell.note} maxLength={maxNoteLength} placeholder="Add a note (optional)" disabled={isReadOnly || !day.is_employed}
        aria-label={`${line.project_name} note on ${day.date}`} onChange={event => onNoteChange(line.key, day.date, event.target.value)}
        style={{ height: 34, borderRadius: 8, fontSize: 12.5, border: "1px solid var(--line)", background: "var(--surface)", color: "var(--ink)", padding: "0 10px" }}
      />
    </div>
  );
}

export default function TimesheetProjectCard({ line, days, isReadOnly, maxNoteLength, onHoursChange, onNoteChange, onBillableChange }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const dates = days.map(day => day.date);
  const worked = days.filter(day => (line.cells[day.date]?.hours ?? "").trim() !== "" && isValidHoursText(line.cells[day.date].hours) && Number(line.cells[day.date].hours) > 0);
  return (
    <section aria-label={line.project_name} style={{ border: "1px solid var(--line)", borderRadius: 12, background: "var(--surface)", padding: "12px 14px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 200px", minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: "var(--ink)" }}>{line.project_name}</div>
          {line.project_code && <div style={{ fontSize: 11, color: "var(--muted)" }}>{line.project_code}</div>}
        </div>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--ink-2)" }}>
          <input type="checkbox" checked={line.is_billable} disabled={isReadOnly} aria-label={`${line.project_name} is billable`} onChange={event => onBillableChange(line.key, event.target.checked)} />
          Billable
        </label>
        <div style={{ fontSize: 18, fontWeight: 700, minWidth: 54, textAlign: "right" }} aria-label={`${line.project_name} total hours`}>{formatHours(lineTotal(line, dates))} h</div>
        <button type="button" className="rvbtn" aria-expanded={isOpen} aria-label={`${isOpen ? "Close" : isReadOnly ? "View days for" : "Edit hours for"} ${line.project_name}`} onClick={() => setIsOpen(open => !open)}>
          {isOpen ? "Close" : isReadOnly ? "View days" : "Edit hours"}
        </button>
      </div>
      {!isOpen && (
        <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap", fontSize: 12, color: "var(--muted)" }}>
          {worked.length === 0
            ? <span>No hours yet this week.</span>
            : worked.map(day => <span key={day.date} className="chip">{day.weekday} {formatHours(Number(line.cells[day.date].hours))}</span>)}
        </div>
      )}
      {isOpen && (
        <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
          {days.map(day => <DayRow key={day.date} line={line} day={day} isReadOnly={isReadOnly} maxNoteLength={maxNoteLength} onHoursChange={onHoursChange} onNoteChange={onNoteChange} />)}
        </div>
      )}
    </section>
  );
}
