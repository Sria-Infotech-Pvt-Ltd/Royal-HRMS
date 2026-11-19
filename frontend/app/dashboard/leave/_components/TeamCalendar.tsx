"use client";

import { useState, type CSSProperties } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { LeaveTypeKey, LEAVE_TYPE_CONFIG } from "../_data";
import { LeaveStyles } from "./leaveStyles";
import { tr } from "@/lib/i18n/tr";

interface CalEvent {
  id:                  string;
  employee_name:       string;
  employee_code:       string;
  leave_type:          LeaveTypeKey;
  leave_type_display:  string;
  start_date:          string;
  end_date:            string;
  total_days:          number;
}

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DAY_NAMES   = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
const PILLS_PER_DAY = 2;

function eventColor(leaveType: LeaveTypeKey): string {
  return LEAVE_TYPE_CONFIG[leaveType]?.color ?? "var(--primary)";
}

function isoDay(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/** Leaves covering one calendar day. ISO dates compare correctly as plain strings. */
function dayEvents(events: CalEvent[], iso: string): CalEvent[] {
  return events.filter(e => e.start_date <= iso && iso <= e.end_date);
}

function initialsOf(name: string): string {
  return name.split(" ").filter(Boolean).slice(0, 2).map(part => part[0]?.toUpperCase() ?? "").join("") || "?";
}

function shortDate(iso: string): string {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function LeaveRow({ event }: { event: CalEvent }) {
  return (
    <div className="lv-row" style={{ "--lv-accent": eventColor(event.leave_type) } as CSSProperties}>
      <span className="lv-avatar">{initialsOf(event.employee_name)}</span>
      <div className="lv-row-main">
        <div className="lv-row-title">{event.employee_name}</div>
        <div className="lv-row-meta">{event.leave_type_display} · {shortDate(event.start_date)}{event.start_date === event.end_date ? "" : ` - ${shortDate(event.end_date)}`}</div>
      </div>
      <span className="lv-chip">{tr(event.total_days === 1 ? "{count} day" : "{count} days", { count: event.total_days })}</span>
    </div>
  );
}

export default function TeamCalendar() {
  const now = new Date();
  const [year,  setYear]  = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [selected, setSelected] = useState<string | null>(null);

  const { data: events, loading } = useFetch<CalEvent[]>(
    API.leave.calendar + `?year=${year}&month=${month + 1}`
  );

  const allEvents = events ?? [];
  const firstDay    = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: Array<number | null> = [
    ...Array<null>(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const todayIso = isoDay(now.getFullYear(), now.getMonth(), now.getDate());
  const peopleAway = new Set(allEvents.map(e => e.employee_code || e.employee_name)).size;
  const leaveDays = allEvents.reduce((sum, e) => sum + Number(e.total_days), 0);
  const usedTypes = [...new Set(allEvents.map(e => e.leave_type))];
  const selectedEvents = selected ? dayEvents(allEvents, selected) : [];

  function goTo(nextYear: number, nextMonth: number) {
    setYear(nextYear);
    setMonth(nextMonth);
    setSelected(null);
  }
  function prev() {
    if (month === 0) goTo(year - 1, 11);
    else goTo(year, month - 1);
  }
  function next() {
    if (month === 11) goTo(year + 1, 0);
    else goTo(year, month + 1);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <LeaveStyles />

      <div className="lv-panel">
        <div className="lv-panel-head">
          <div className="lv-cal-nav">
            <button className="lv-cal-btn" onClick={prev} aria-label={tr("Previous month")}><i className="ti ti-chevron-left" /></button>
            <span className="lv-cal-title">{MONTH_NAMES[month]} {year}</span>
            <button className="lv-cal-btn" onClick={next} aria-label={tr("Next month")}><i className="ti ti-chevron-right" /></button>
            <button className="lv-cal-btn" onClick={() => goTo(now.getFullYear(), now.getMonth())}>{tr("Today")}</button>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span className="lv-chip" style={{ "--lv-accent": "var(--brand)" } as CSSProperties}><i className="ti ti-users" /> {peopleAway} {tr("away")}</span>
            <span className="lv-chip" style={{ "--lv-accent": "#0ea5e9" } as CSSProperties}><i className="ti ti-calendar-stats" /> {tr(leaveDays === 1 ? "{count} leave day" : "{count} leave days", { count: leaveDays })}</span>
          </div>
        </div>

        <div className="lv-cal-grid">
          {DAY_NAMES.map(d => <div key={d} className="lv-cal-dow">{d.toUpperCase()}</div>)}
        </div>

        {loading ? (
          <div className="lv-empty"><i className="ti ti-loader-2" /></div>
        ) : (
          <div className="lv-cal-grid">
            {cells.map((day, idx) => {
              if (!day) return <div key={idx} className="lv-cal-cell is-empty" />;
              const iso = isoDay(year, month, day);
              const ev = dayEvents(allEvents, iso);
              const classes = [
                "lv-cal-cell",
                idx % 7 === 0 || idx % 7 === 6 ? "is-weekend" : "",
                iso === todayIso ? "is-today" : "",
                iso < todayIso ? "is-past" : "",
                ev.length > 0 ? "has-leave" : "",
                iso === selected ? "is-selected" : "",
              ].filter(Boolean).join(" ");
              return (
                <button
                  key={idx}
                  type="button"
                  className={classes}
                  disabled={ev.length === 0}
                  aria-label={`${day} ${MONTH_NAMES[month]}${ev.length ? `, ${ev.length} on leave` : ""}`}
                  onClick={() => setSelected(iso === selected ? null : iso)}
                >
                  <span className="lv-cal-num">{day}</span>
                  {ev.slice(0, PILLS_PER_DAY).map(e => (
                    <span key={e.id} className="lv-cal-pill" title={`${e.employee_name} – ${e.leave_type_display}`} style={{ background: eventColor(e.leave_type) }}>
                      {e.employee_name.split(" ")[0]}
                    </span>
                  ))}
                  {ev.length > PILLS_PER_DAY && <span className="lv-cal-more">+{ev.length - PILLS_PER_DAY} {tr("more")}</span>}
                </button>
              );
            })}
          </div>
        )}

        {usedTypes.length > 0 && (
          <div className="lv-panel-body" style={{ borderTop: "1px solid var(--outline-v)" }}>
            <div className="lv-legend">
              {usedTypes.map(type => (
                <span key={type}><i style={{ background: eventColor(type) }} />{LEAVE_TYPE_CONFIG[type]?.label ?? type}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {selected && (
        <div className="lv-panel">
          <div className="lv-panel-head">
            <span><i className="ti ti-user-off" /> {tr("Away on {date}", { date: shortDate(selected) })}</span>
            <button className="lv-cal-btn" onClick={() => setSelected(null)} aria-label={tr("Close day details")}><i className="ti ti-x" /></button>
          </div>
          {selectedEvents.map(e => <LeaveRow key={e.id} event={e} />)}
        </div>
      )}

      {allEvents.length > 0 && (
        <div className="lv-panel">
          <div className="lv-panel-head"><span><i className="ti ti-calendar-event" /> {tr("Leaves this month")}</span><span className="lv-chip">{allEvents.length}</span></div>
          {allEvents.map(e => <LeaveRow key={e.id} event={e} />)}
        </div>
      )}

      {!loading && allEvents.length === 0 && (
        <div className="lv-panel">
          <div className="lv-empty"><i className="ti ti-calendar-off" />{tr("No approved leaves for {month} {year}.", { month: MONTH_NAMES[month], year })}</div>
        </div>
      )}
    </div>
  );
}
