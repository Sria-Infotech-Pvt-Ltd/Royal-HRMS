"use client";

// Monthly attendance calendar for the ESS Attendance tab: a Sunday-first month
// grid with one dot + short label per day. Colours come from the existing
// .ess-status-dot classes (ess-theme.css) through dayClass(); the data is the
// unchanged calendar.days map from useAttendanceDashboard.

import { useState, type SyntheticEvent } from "react";
import { buildMonthGrid, isoDate, WEEKDAY_SHORT } from "@/lib/attendanceCalendarGrid";
import type { DayRecord } from "@/types/attendance";

const MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

const LEGEND: ReadonlyArray<[string, string]> = [
  ["present", "Present"],
  ["late", "Late"],
  ["absent", "Absent"],
  ["half-day", "Half day"],
  ["leave", "On leave"],
  ["unrecorded", "Week off / Holiday"],
  ["incomplete", "Incomplete"],
  ["not-joined", "Not joined"],
];

/** Maps the backend's display status to the colour class used by .ess-status-dot. */
export function dayClass(status: string | undefined): string {
  const value = (status ?? "").toLowerCase();
  if (value === "present") return "present";
  if (value === "late") return "late";
  if (value === "absent") return "absent";
  if (value === "half day") return "half-day";
  if (value.includes("leave")) return "leave";
  if (value === "weekly off") return "weekly-off";
  if (value === "holiday") return "holiday";
  if (value === "incomplete" || value === "missing clock out") return "incomplete";
  if (value === "not joined") return "not-joined";
  return "unrecorded";
}

const NON_WORKING = new Set(["weekly-off", "holiday", "not-joined"]);

interface EssAttendanceCalendarProps {
  year: number;
  /** 1-12 */
  month: number;
  /** calendar.days from the attendance dashboard, keyed by day of month ("1", "2", …). */
  calendar: Record<string, DayRecord>;
  isLoading: boolean;
  onPreviousMonth: () => void;
  onNextMonth: () => void;
  onToday: () => void;
}

function dayTitle(day: number, monthName: string, year: number, record: DayRecord | undefined): string {
  const parts = [`${day} ${monthName} ${year}`];
  if (record?.status) parts.push(record.holiday_name ? `${record.status}: ${record.holiday_name}` : record.status);
  if (record?.clockIn) parts.push(`In ${record.clockIn}${record.clockOut ? ` · Out ${record.clockOut}` : ""}`);
  return parts.join(" — ");
}

const TIP_WIDTH = 190;
const TIP_GAP = 6;
const TIP_HEIGHT_ESTIMATE = 130;

interface TipPosition { left: number; top: number }

/** Hover card for one day: punch in, punch out and hours. Fixed-positioned so the grid's overflow:hidden cannot clip it. */
function DayTip({ heading, record, position }: { heading: string; record: DayRecord | undefined; position: TipPosition }) {
  const hasPunch = Boolean(record?.clockIn || record?.clockOut);
  return (
    <div className="ess-cal-tip" role="tooltip" style={{ left: position.left, top: position.top, width: TIP_WIDTH }}>
      <strong>{heading}</strong>
      {record?.status && <span className="ess-cal-tip-status">{record.holiday_name ? `${record.status}: ${record.holiday_name}` : record.status}</span>}
      {hasPunch ? (
        <dl>
          <dt>Punched in</dt><dd>{record?.clockIn || "—"}</dd>
          <dt>Punched out</dt><dd>{record?.clockOut || "—"}</dd>
          {record?.hours && (<><dt>Hours</dt><dd>{record.hours}</dd></>)}
        </dl>
      ) : (
        <span className="ess-cal-tip-empty">No punches recorded</span>
      )}
    </div>
  );
}

function DayCell({ day, year, month, record, isToday }: {
  day: number; year: number; month: number; record: DayRecord | undefined; isToday: boolean;
}) {
  const [tipPosition, setTipPosition] = useState<TipPosition | null>(null);
  const statusClass = dayClass(record?.status);
  const label = record?.holiday_name || record?.status || "";
  const title = dayTitle(day, MONTH_LONG[month - 1], year, record);

  function showTip(event: SyntheticEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const left = Math.min(Math.max(8, rect.left + rect.width / 2 - TIP_WIDTH / 2), window.innerWidth - TIP_WIDTH - 8);
    const isRoomBelow = rect.bottom + TIP_GAP + TIP_HEIGHT_ESTIMATE < window.innerHeight;
    setTipPosition({ left, top: isRoomBelow ? rect.bottom + TIP_GAP : Math.max(8, rect.top - TIP_GAP - TIP_HEIGHT_ESTIMATE) });
  }

  return (
    <div
      role="cell"
      tabIndex={0}
      className={`ess-cal-cell${NON_WORKING.has(statusClass) ? " non-working" : ""}${isToday ? " today" : ""}`}
      data-date={isoDate(year, month, day)}
      aria-label={title}
      onMouseEnter={showTip}
      onMouseLeave={() => setTipPosition(null)}
      onFocus={showTip}
      onBlur={() => setTipPosition(null)}
    >
      <span className="ess-cal-date" aria-current={isToday ? "date" : undefined}>{day}</span>
      {label && (
        <span className="ess-cal-status">
          <i className={`ess-status-dot ${statusClass}`} aria-hidden="true" />
          <span className="ess-cal-label">{label}</span>
        </span>
      )}
      {tipPosition && <DayTip heading={`${day} ${MONTH_LONG[month - 1]} ${year}`} record={record} position={tipPosition} />}
    </div>
  );
}

export default function EssAttendanceCalendar({
  year, month, calendar, isLoading, onPreviousMonth, onNextMonth, onToday,
}: EssAttendanceCalendarProps) {
  const now = new Date();
  const isCurrentMonth = now.getFullYear() === year && now.getMonth() + 1 === month;
  const weeks = buildMonthGrid(year, month);

  return (
    <div className="ess-cal">
      <div className="ess-cal-head">
        <div>
          <h2>{MONTH_LONG[month - 1]} {year}</h2>
          <p>Daily attendance and approved leave.</p>
        </div>
        <div className="ess-cal-nav">
          <button className="rvbtn" type="button" onClick={onToday} disabled={isLoading || isCurrentMonth}>
            Today
          </button>
          <button className="rvbtn ess-cal-arrow" type="button" onClick={onPreviousMonth} disabled={isLoading} aria-label="Previous month">
            <i className="ti ti-chevron-left" />
          </button>
          <button className="rvbtn ess-cal-arrow" type="button" onClick={onNextMonth} disabled={isLoading} aria-label="Next month">
            <i className="ti ti-chevron-right" />
          </button>
        </div>
      </div>

      <div className="ess-calendar-legend" aria-label="Attendance status colors">
        {LEGEND.map(([className, label]) => (
          <span key={className}><i className={`ess-status-dot ${className}`} />{label}</span>
        ))}
      </div>

      <div
        className="ess-cal-grid"
        role="table"
        aria-label={`Attendance for ${MONTH_LONG[month - 1]} ${year}`}
        aria-busy={isLoading}
      >
        <div className="ess-cal-row ess-cal-weekdays" role="row">
          {WEEKDAY_SHORT.map(name => <span key={name} role="columnheader">{name}</span>)}
        </div>
        {weeks.map((week, row) => (
          <div className="ess-cal-row" role="row" key={row}>
            {week.map((day, column) => day === null
              ? <div key={column} role="cell" className="ess-cal-cell outside" aria-hidden="true" />
              : (
                <DayCell
                  key={column}
                  day={day}
                  year={year}
                  month={month}
                  record={calendar[String(day)]}
                  isToday={isCurrentMonth && day === now.getDate()}
                />
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}
