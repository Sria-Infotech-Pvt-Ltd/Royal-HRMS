"use client";

// The week as a short list: one card per project (plus Internal work), then a compact strip with the hours per day and the
// attendance hours from punches, kept apart from the project hours the person types. Editable for the employee, read-only for a
// submitted or approved sheet and for the approver's drawer.

import type { GridLine, TimesheetDay, TimesheetLimits } from "@/types/timesheet";
import TimesheetDayStrip from "./TimesheetDayStrip";
import TimesheetProjectCard from "./TimesheetProjectCard";

interface Props {
  days: TimesheetDay[];
  lines: GridLine[];
  limits: TimesheetLimits;
  isReadOnly: boolean;
  onHoursChange: (lineKey: string, date: string, text: string) => void;
  onNoteChange: (lineKey: string, date: string, text: string) => void;
  onBillableChange: (lineKey: string, isBillable: boolean) => void;
}

export default function TimesheetProjects({ days, lines, limits, isReadOnly, onHoursChange, onNoteChange, onBillableChange }: Props) {
  return (
    <div style={{ display: "grid", gap: 12 }}>
      {lines.map(line => (
        <TimesheetProjectCard
          key={line.key} line={line} days={days} isReadOnly={isReadOnly} maxNoteLength={limits.max_note_length}
          onHoursChange={onHoursChange} onNoteChange={onNoteChange} onBillableChange={onBillableChange}
        />
      ))}
      <TimesheetDayStrip days={days} lines={lines} limits={limits} />
    </div>
  );
}
