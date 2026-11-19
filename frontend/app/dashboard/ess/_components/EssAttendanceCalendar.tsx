"use client";

// Monthly attendance calendar for the ESS Attendance tab: a Sunday-first month
// grid with one dot + short label per day. Colours come from the existing
// .ess-status-dot classes (ess-theme.css) through dayClass(); the data is the
// unchanged calendar.days map from useAttendanceDashboard.

import { useState, type SyntheticEvent } from "react";
import { buildMonthGrid, isoDate, WEEKDAY_SHORT } from "@/lib/attendanceCalendarGrid";
import { isWorkFromHome } from "@/lib/workMode";
import { shortHoursText } from "@/lib/shortHours";
import { LATE_LOGIN_LABEL, LATE_LOGIN_MEANING, isLateLogin, lateLoginText } from "@/lib/lateLogin";
import type { DayRecord } from "@/types/attendance";
import { tr } from "@/lib/i18n/tr";

const MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

interface LegendEntry { className: string; label: string; meaning: string }

/** Every colour the calendar can show, with what it means. The inline legend lists only the ones present in the month. */
const LEGEND: ReadonlyArray<LegendEntry> = [
  { className: "present",    get label() { return tr("Present"); },            meaning: "A full working day." },
  { className: "late",       get label() { return tr("Late"); },               meaning: "Arrived after the grace time." },
  { className: "absent",     get label() { return tr("Absent"); },             meaning: "No attendance recorded on a working day." },
  { className: "half-day",   get label() { return tr("Half day"); },           meaning: "Worked up to the half-day limit." },
  { className: "leave",      get label() { return tr("On leave"); },           meaning: "Approved leave." },
  { className: "unrecorded", get label() { return tr("Week off / Holiday"); }, meaning: "Not a working day." },
  { className: "incomplete", get label() { return tr("Incomplete"); },         meaning: "Punched in but never punched out. Raise a correction so the day gets its hours." },
];
const WFH_MEANING = "Worked from home (approved request).";
const SHORT_MEANING = "Hours not completed: worked more than a half day but less than a full day. The tag shows how many minutes short.";

/** The legend class a day's status colour belongs to (week off and holiday share one entry). */
function legendClassFor(statusClass: string): string {
  return statusClass === "weekly-off" || statusClass === "holiday" ? "unrecorded" : statusClass;
}

/** What the month actually contains, so the legend lists only that. */
function usedInMonth(calendar: Record<string, DayRecord>): { classes: Set<string>; hasWfh: boolean; hasShort: boolean; hasLateLogin: boolean } {
  const classes = new Set<string>();
  let hasWfh = false;
  let hasShort = false;
  let hasLateLogin = false;
  for (const record of Object.values(calendar)) {
    const statusClass = dayClass(record.status);
    if (statusClass !== "not-joined") classes.add(legendClassFor(statusClass));
    hasWfh = hasWfh || isWorkFromHome(record);
    hasShort = hasShort || shortHoursText(record) !== null;
    hasLateLogin = hasLateLogin || isLateLogin(record);
  }
  return { classes, hasWfh, hasShort, hasLateLogin };
}

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
  // The backend labels days outside the employment window "Not Employed" (STATUS_DISPLAY_MAP); the legend calls it "Not joined".
  if (value === "not joined" || value === "not employed") return "not-joined";
  return "unrecorded";
}

const NON_WORKING = new Set(["weekly-off", "holiday", "not-joined"]);
// Working-day statuses whose whole cell is tinted in the status colour (see .st-* in ess-theme.css).
const TINTED = new Set(["present", "late", "absent", "half-day", "leave", "incomplete"]);

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
  if (isWorkFromHome(record)) parts.push("Work from home");
  const short = shortHoursText(record);
  if (short) parts.push(`Hours not completed (short by ${short})`);
  if (isLateLogin(record)) parts.push(tr(LATE_LOGIN_LABEL));
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
      {isWorkFromHome(record) && <span className="ess-cal-wfh"><i className="ti ti-home" aria-hidden="true" /> {tr("Work from home")}</span>}
      {shortHoursText(record) && (
        <span className="ess-cal-short"><i className="ti ti-alert-triangle" aria-hidden="true" /> {tr("Hours not completed: short by {time}", { time: shortHoursText(record) ?? "" })}</span>
      )}
      {lateLoginText(record) && (
        <span className="ess-cal-late"><i className="ti ti-clock-exclamation" aria-hidden="true" /> {tr(LATE_LOGIN_LABEL)}: {lateLoginText(record)}</span>
      )}
      {hasPunch ? (
        <dl>
          <dt>{tr("Punched in")}</dt><dd>{record?.clockIn || "—"}</dd>
          <dt>{tr("Punched out")}</dt><dd>{record?.clockOut || "—"}</dd>
          {record?.hours && (<><dt>{tr("Hours")}</dt><dd>{record.hours}</dd></>)}
        </dl>
      ) : (
        <span className="ess-cal-tip-empty">{tr("No punches recorded")}</span>
      )}
    </div>
  );
}

function DayCell({ day, year, month, record: rawRecord, isToday }: {
  day: number; year: number; month: number; record: DayRecord | undefined; isToday: boolean;
}) {
  const [tipPosition, setTipPosition] = useState<TipPosition | null>(null);
  // Days outside the employment window (before joining / after last working day) are left blank, not labelled.
  const isOutsideEmployment = ["not employed", "not joined"].includes((rawRecord?.status ?? "").toLowerCase());
  const record = isOutsideEmployment ? undefined : rawRecord;
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
      className={`ess-cal-cell${TINTED.has(statusClass) ? ` st-${statusClass}` : ""}${NON_WORKING.has(statusClass) ? " non-working" : ""}${isToday ? " today" : ""}`}
      data-date={isoDate(year, month, day)}
      aria-label={title}
      onMouseEnter={showTip}
      onMouseLeave={() => setTipPosition(null)}
      onFocus={showTip}
      onBlur={() => setTipPosition(null)}
    >
      <span className="ess-cal-date" aria-current={isToday ? "date" : undefined}>{day}</span>
      {label && (
        <span className={`ess-cal-status ${statusClass}`}>
          <i className={`ess-status-dot ${statusClass}`} aria-hidden="true" />
          <span className="ess-cal-label">{label}</span>
        </span>
      )}
      {(isWorkFromHome(record) || shortHoursText(record) || isLateLogin(record)) && (
        <div className="ess-cal-tags">
          {isWorkFromHome(record) && (
            <span className="ess-cal-wfh" title={tr("Work from home")}>
              <i className="ti ti-home" aria-hidden="true" /><span className="ess-cal-tag-text">{tr("WFH")}</span>
            </span>
          )}
          {shortHoursText(record) && (
            <span className="ess-cal-short" title={`Hours not completed: short by ${shortHoursText(record)}`}>
              <i className="ti ti-alert-triangle" aria-hidden="true" /><span className="ess-cal-tag-text">{tr("Short")} {shortHoursText(record)}</span>
            </span>
          )}
          {isLateLogin(record) && (
            <span className="ess-cal-late" title={lateLoginText(record) ?? tr(LATE_LOGIN_LABEL)}>
              <i className="ti ti-clock-exclamation" aria-hidden="true" /><span className="ess-cal-tag-text">{tr(LATE_LOGIN_LABEL)}</span>
            </span>
          )}
        </div>
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
  const used = usedInMonth(calendar);

  return (
    <div className="ess-cal">
      <div className="ess-cal-head">
        <div>
          <h2>{MONTH_LONG[month - 1]} {year}</h2>
          <p>{tr("Daily attendance and approved leave.")}</p>
        </div>
        <div className="ess-cal-nav">
          <button className="rvbtn" type="button" onClick={onToday} disabled={isLoading || isCurrentMonth}>
            {tr("Today")}
          </button>
          <button className="rvbtn ess-cal-arrow" type="button" onClick={onPreviousMonth} disabled={isLoading} aria-label={tr("Previous month")}>
            <i className="ti ti-chevron-left" />
          </button>
          <button className="rvbtn ess-cal-arrow" type="button" onClick={onNextMonth} disabled={isLoading} aria-label={tr("Next month")}>
            <i className="ti ti-chevron-right" />
          </button>
        </div>
      </div>

      <div className="ess-calendar-legend" aria-label={tr("Attendance status colors")}>
        {LEGEND.filter(entry => used.classes.has(entry.className)).map(entry => (
          <span key={entry.className} title={entry.meaning}><i className={`ess-status-dot ${entry.className}`} />{entry.label}</span>
        ))}
        {used.hasWfh && (
          <span title={WFH_MEANING}>
            <span className="ess-cal-wfh"><i className="ti ti-home" aria-hidden="true" /><span className="ess-cal-tag-text">{tr("WFH")}</span></span>{tr("Work from home")}
          </span>
        )}
        {used.hasLateLogin && (
          <span title={tr(LATE_LOGIN_MEANING)}>
            <span className="ess-cal-late"><i className="ti ti-clock-exclamation" aria-hidden="true" /><span className="ess-cal-tag-text">{tr(LATE_LOGIN_LABEL)}</span></span>{tr("Arrived late, full day worked")}
          </span>
        )}
        {used.hasShort && (
          <span title={SHORT_MEANING}>
            <span className="ess-cal-short"><i className="ti ti-alert-triangle" aria-hidden="true" /><span className="ess-cal-tag-text">{tr("Short")}</span></span>{tr("Hours not completed")}
          </span>
        )}
      </div>
      <details className="ess-cal-key">
        <summary>{tr("What do these mean?")}</summary>
        <dl>
          {LEGEND.map(entry => (
            <div key={entry.className} className="ess-cal-key-row">
              <dt><i className={`ess-status-dot ${entry.className}`} />{entry.label}</dt>
              <dd>{entry.meaning}</dd>
            </div>
          ))}
          <div className="ess-cal-key-row">
            <dt><span className="ess-cal-wfh"><i className="ti ti-home" aria-hidden="true" /><span className="ess-cal-tag-text">{tr("WFH")}</span></span>{tr("Work from home")}</dt>
            <dd>{WFH_MEANING}</dd>
          </div>
          <div className="ess-cal-key-row">
            <dt><span className="ess-cal-late"><i className="ti ti-clock-exclamation" aria-hidden="true" /><span className="ess-cal-tag-text">{tr(LATE_LOGIN_LABEL)}</span></span>{tr("Arrived late")}</dt>
            <dd>{tr(LATE_LOGIN_MEANING)}</dd>
          </div>
          <div className="ess-cal-key-row">
            <dt><span className="ess-cal-short"><i className="ti ti-alert-triangle" aria-hidden="true" /><span className="ess-cal-tag-text">{tr("Short")}</span></span>{tr("Hours not completed")}</dt>
            <dd>{SHORT_MEANING}</dd>
          </div>
        </dl>
      </details>

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
