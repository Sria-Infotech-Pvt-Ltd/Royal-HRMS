"use client";

import { useState } from "react";
import CalendarGrid, { type DayRecord } from "../../my-calendar/_components/CalendarGrid";
import MonthDetail from "../../my-calendar/_components/MonthDetail";

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
  { label: "Present",    bg: "var(--success-c)", color: "var(--success)"   },
  { label: "Late",       bg: "var(--warn-c)",    color: "var(--warn)"      },
  { label: "Absent",     bg: "var(--error-c)",   color: "var(--error)"     },
  { label: "On Leave",   bg: "var(--info-c)",    color: "var(--info)"      },
  { label: "Half Day",   bg: "rgba(30,78,140,0.10)", color: "var(--primary)" },
  { label: "Weekly Off", bg: "var(--bg-low)",    color: "var(--outline)"   },
  { label: "Holiday",    bg: "var(--sec-c)",     color: "var(--secondary)" },
];

export default function MyCalendarTab() {
  const now = new Date();
  const [year,  setYear]  = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  function prev() {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  }
  function next() {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  }

  const key  = `${year}-${month}`;
  const data = ALL_DATA[key] ?? {};

  return (
    <div>
      {/* Month navigation */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {LEGEND.map(item => (
            <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 5, padding: "3px 10px", background: item.bg, border: "1px solid var(--outline-v)", borderRadius: 6 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: item.color, display: "inline-block", flexShrink: 0 }} />
              <span style={{ fontSize: 11, fontWeight: 500, color: item.color }}>{item.label}</span>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          <button className="btn btn-ghost btn-sm" onClick={prev}>
            <i className="ti ti-chevron-left" />
          </button>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", minWidth: 120, textAlign: "center" }}>
            {MONTH_NAMES[month]} {year}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={next}>
            <i className="ti ti-chevron-right" />
          </button>
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <CalendarGrid year={year} month={month} data={data} />
      </div>

      <MonthDetail year={year} month={month} data={data} />
    </div>
  );
}
