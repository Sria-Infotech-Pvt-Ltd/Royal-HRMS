"use client";

// The date control of the Team Day View: previous and next day, the date itself (typed or from the calendar icon), a caption that says
// which weekday it is and how long ago, and one-click Today / Yesterday buttons. Dates move in the viewer's own calendar days.

import DateInput from "@/components/shared/DateInput";
import { relativeDayLabel, shiftISODate, weekdayName } from "./attendanceDates";

interface Props {
  date: string;
  todayISO: string;
  onChange: (isoDate: string) => void;
  /** Whether dates after today may be chosen (the OT form allows them; the attendance screens do not). */
  allowFuture?: boolean;
}

export default function AttendanceDatePicker({ date, todayISO, onChange, allowFuture = false }: Props) {
  const yesterday = shiftISODate(todayISO, -1);
  const quick = [{ label: "Today", value: todayISO }, { label: "Yesterday", value: yesterday }];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 4, padding: 4, borderRadius: 12, background: "var(--surface)", border: "1px solid var(--outline-v)" }}>
        <button className="btn btn-ghost btn-sm" style={{ padding: "0 8px", border: 0 }} onClick={() => onChange(shiftISODate(date, -1))} aria-label="Previous day" title="Previous day">
          <i className="ti ti-chevron-left" />
        </button>
        <DateInput className="field-input" style={{ width: 150, border: 0, fontWeight: 600 }} value={date} max={allowFuture ? undefined : todayISO} onChange={onChange} />
        <button className="btn btn-ghost btn-sm" style={{ padding: "0 8px", border: 0 }} disabled={!allowFuture && date >= todayISO} onClick={() => onChange(shiftISODate(date, 1))} aria-label="Next day" title="Next day">
          <i className="ti ti-chevron-right" />
        </button>
      </div>
      {date && (
        <span aria-live="polite" style={{ fontSize: 12.5, color: "var(--on-variant)", minWidth: 96 }}>
          <strong style={{ color: "var(--on-bg)", fontWeight: 600 }}>{weekdayName(date)}</strong>
          {/* Today and Yesterday are already named by the highlighted button beside it, so only other dates get "4 days ago". */}
          {date !== todayISO && date !== yesterday && ` · ${relativeDayLabel(date, todayISO)}`}
        </span>
      )}
      <div role="group" aria-label="Quick dates" style={{ display: "flex", gap: 6 }}>
        {quick.map(item => (
          <button
            key={item.label} type="button" aria-pressed={date === item.value} onClick={() => onChange(item.value)}
            className={date === item.value ? "btn btn-filled btn-sm" : "btn btn-ghost btn-sm"}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
