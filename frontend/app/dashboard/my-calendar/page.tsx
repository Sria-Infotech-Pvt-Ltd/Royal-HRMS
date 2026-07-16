"use client";

import { useState } from "react";
import CalendarGrid, { type DayRecord } from "./_components/CalendarGrid";
import MonthDetail from "./_components/MonthDetail";

// ── Static mock data (June 2025) ──────────────────────────────────────────────

const JUNE_2025: Record<number, DayRecord> = {
  1:  { status: "Weekly Off" },
  2:  { status: "Present",    clockIn: "09:03", clockOut: "18:10", hours: "9h 07m" },
  3:  { status: "Present",    clockIn: "09:00", clockOut: "18:05", hours: "9h 05m" },
  4:  { status: "Present",    clockIn: "08:58", clockOut: "18:15", hours: "9h 17m" },
  5:  { status: "Present",    clockIn: "09:05", clockOut: "18:00", hours: "8h 55m" },
  6:  { status: "Late",       clockIn: "09:48", clockOut: "18:30", hours: "8h 42m", note: "Grace exceeded" },
  7:  { status: "Weekly Off" },
  8:  { status: "Weekly Off" },
  9:  { status: "Present",    clockIn: "09:02", clockOut: "18:10", hours: "9h 08m" },
  10: { status: "Present",    clockIn: "09:00", clockOut: "18:00", hours: "9h 00m" },
  11: { status: "Present",    clockIn: "08:55", clockOut: "18:20", hours: "9h 25m" },
  12: { status: "Absent",     note: "No punch recorded" },
  13: { status: "Present",    clockIn: "09:10", clockOut: "18:05", hours: "8h 55m" },
  14: { status: "Weekly Off" },
  15: { status: "Weekly Off" },
  16: { status: "Holiday",    note: "Eid al-Adha" },
  17: { status: "Present",    clockIn: "09:00", clockOut: "18:00", hours: "9h 00m" },
  18: { status: "Present",    clockIn: "09:04", clockOut: "18:10", hours: "9h 06m" },
  19: { status: "Present",    clockIn: "09:00", clockOut: "18:15", hours: "9h 15m" },
  20: { status: "Present",    clockIn: "09:00", clockOut: "18:00", hours: "9h 00m" },
  21: { status: "Weekly Off" },
  22: { status: "Weekly Off" },
  23: { status: "Half Day",   clockIn: "09:05", clockOut: "13:10", hours: "4h 05m", note: "Afternoon off" },
  24: { status: "Present",    clockIn: "08:58", clockOut: "18:05", hours: "9h 07m" },
  25: { status: "On Leave",   note: "Casual Leave" },
  26: { status: "On Leave",   note: "Casual Leave" },
  27: { status: "Late",       clockIn: "09:42", clockOut: "18:30", hours: "8h 48m", note: "Traffic delay" },
  28: { status: "Weekly Off" },
  29: { status: "Weekly Off" },
  30: { status: "Present",    clockIn: "09:00", clockOut: "18:00", hours: "9h 00m" },
};

const ALL_DATA: Record<string, Record<number, DayRecord>> = { "2025-6": JUNE_2025 };

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];

const LEGEND = [
  { status: "Present",     bg: "var(--success-c)",        color: "var(--success)"   },
  { status: "Late",        bg: "var(--warn-c)",            color: "var(--warn)"      },
  { status: "Absent",      bg: "var(--error-c)",           color: "var(--error)"     },
  { status: "On Leave",    bg: "var(--info-c)",            color: "var(--info)"      },
  { status: "Half Day",    bg: "rgba(30,78,140,0.10)",     color: "var(--primary)"   },
  { status: "Weekly Off",  bg: "var(--bg-low)",            color: "var(--outline)"   },
  { status: "Holiday",     bg: "var(--sec-c)",             color: "var(--secondary)" },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function MyCalendarPage() {
  const now   = new Date();
  const [year,  setYear]  = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  const key  = `${year}-${month}`;
  const data = ALL_DATA[key] ?? {};
  const records = Object.values(data);

  const counts = {
    present:   records.filter(r => r.status === "Present").length,
    late:      records.filter(r => r.status === "Late").length,
    absent:    records.filter(r => r.status === "Absent").length,
    onLeave:   records.filter(r => r.status === "On Leave").length,
    halfDay:   records.filter(r => r.status === "Half Day").length,
    holiday:   records.filter(r => r.status === "Holiday").length,
    weeklyOff: records.filter(r => r.status === "Weekly Off").length,
  };

  const workingDays = counts.present + counts.late + counts.absent + counts.halfDay;
  const attendancePct = workingDays > 0
    ? Math.round(((counts.present + counts.late + counts.halfDay * 0.5) / workingDays) * 100)
    : 0;

  function prev() {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  }
  function next() {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  }

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-title">My Calendar</div>
          <div className="page-sub">Your personal attendance calendar — present, absent, leaves and holidays</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost btn-sm" onClick={prev}>
            <i className="ti ti-chevron-left" />
          </button>
          <span style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", minWidth: 140, textAlign: "center" }}>
            {MONTH_NAMES[month]} {year}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={next}>
            <i className="ti ti-chevron-right" />
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="stats-grid mb-24">
        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Days Present</div>
              <div className="stat-value" style={{ color: "var(--success)" }}>{counts.present + counts.late}</div>
              <div className="stat-sub">incl. {counts.late} late</div>
            </div>
            <div className="stat-icon si-success"><i className="ti ti-user-check" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${attendancePct}%`, background: "var(--success)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Absent</div>
              <div className="stat-value" style={{ color: "var(--error)" }}>{counts.absent}</div>
              <div className="stat-sub">No punch recorded</div>
            </div>
            <div className="stat-icon si-error"><i className="ti ti-user-off" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: counts.absent > 0 ? "20%" : "0%", background: "var(--error)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Leave Days</div>
              <div className="stat-value" style={{ color: "var(--info)" }}>{counts.onLeave}</div>
              <div className="stat-sub">+ {counts.halfDay} half day{counts.halfDay !== 1 ? "s" : ""}</div>
            </div>
            <div className="stat-icon si-info"><i className="ti ti-beach" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: counts.onLeave > 0 ? "30%" : "0%", background: "var(--info)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Attendance %</div>
              <div className="stat-value" style={{ color: attendancePct >= 90 ? "var(--success)" : "var(--warn)" }}>
                {attendancePct}%
              </div>
              <div className="stat-sub">{counts.holiday} holiday{counts.holiday !== 1 ? "s" : ""} this month</div>
            </div>
            <div className="stat-icon si-primary"><i className="ti ti-chart-pie" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${attendancePct}%`, background: attendancePct >= 90 ? "var(--success)" : "var(--warn)" }} />
          </div>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 16 }}>
        {LEGEND.map(item => (
          <div key={item.status} style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 10px", background: item.bg, border: "1px solid var(--outline-v)", borderRadius: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: item.color, display: "inline-block", flexShrink: 0 }} />
            <span style={{ fontSize: 11, fontWeight: 500, color: item.color }}>{item.status}</span>
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div style={{ marginBottom: 16 }}>
        <CalendarGrid year={year} month={month} data={data} />
      </div>

      {/* Month detail table */}
      <MonthDetail year={year} month={month} data={data} />
    </div>
  );
}
