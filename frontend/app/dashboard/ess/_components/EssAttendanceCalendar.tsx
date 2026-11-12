"use client";

// Monthly attendance calendar for the ESS Attendance tab: a Sunday-first month
// grid with one dot + short label per day. Colours come from the existing
// .ess-status-dot classes (ess-theme.css) through dayClass(); the data is the
// unchanged calendar.days map from useAttendanceDashboard.

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

function DayCell({ day, year, month, record, isToday }: {
  day: number; year: number; month: number; record: DayRecord | undefined; isToday: boolean;
}) {
  const statusClass = dayClass(record?.status);
  const label = record?.holiday_name || record?.status || "";
  const title = dayTitle(day, MONTH_LONG[month - 1], year, record);
  return (
    <div
      role="cell"
      className={`ess-cal-cell${NON_WORKING.has(statusClass) ? " non-working" : ""}${isToday ? " today" : ""}`}
      data-date={isoDate(year, month, day)}
      title={title}
      aria-label={title}
    >
      <span className="ess-cal-date" aria-current={isToday ? "date" : undefined}>{day}</span>
      {label && (
        <span className="ess-cal-status">
          <i className={`ess-status-dot ${statusClass}`} aria-hidden="true" />
          <span className="ess-cal-label">{label}</span>
        </span>
      )}
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
