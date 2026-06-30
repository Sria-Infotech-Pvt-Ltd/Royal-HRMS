"use client";

import type { DayRecord, DayStatus } from "./CalendarGrid";

interface Props {
  year:  number;
  month: number;
  data:  Record<number, DayRecord>;
}

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DAY_ABBR    = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

const BADGE_MAP: Partial<Record<DayStatus, string>> = {
  Present:     "badge badge-success",
  Late:        "badge badge-warn",
  Absent:      "badge badge-error",
  "On Leave":  "badge badge-info",
  "Half Day":  "badge badge-primary",
  "Weekly Off":"badge badge-neutral",
  Holiday:     "badge badge-neutral",
};

export default function MonthDetail({ year, month, data }: Props) {
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const rows = Array.from({ length: daysInMonth }, (_, i) => {
    const day    = i + 1;
    const record = data[day];
    const dow    = new Date(year, month, day).getDay();
    return { day, dow, record };
  }).filter(r => r.record && r.record.status !== "future" && r.record.status !== "empty");

  if (rows.length === 0) return null;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <i className="ti ti-list-details" /> {MONTH_NAMES[month]} {year} — Detail
        </div>
        <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{rows.length} days</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Day</th>
              <th>Clock In</th>
              <th>Clock Out</th>
              <th>Hours</th>
              <th>Status</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ day, dow, record }) => {
              if (!record) return null;
              const isLateIn = record.clockIn && record.clockIn > "09:15";
              return (
                <tr key={day}>
                  <td style={{ fontWeight: 600 }}>
                    {String(day).padStart(2, "0")} {MONTH_NAMES[month].slice(0, 3)}
                  </td>
                  <td style={{ color: "var(--on-variant)" }}>{DAY_ABBR[dow]}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: record.clockIn ? (isLateIn ? "var(--error)" : "var(--on-bg)") : "var(--outline-v)" }}>
                    {record.clockIn ?? "—"}
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: record.clockOut ? "var(--on-bg)" : "var(--outline-v)" }}>
                    {record.clockOut ?? "—"}
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: record.hours ? "var(--on-bg)" : "var(--outline-v)" }}>
                    {record.hours ?? "—"}
                  </td>
                  <td>
                    {BADGE_MAP[record.status] && (
                      <span className={BADGE_MAP[record.status]}>{record.status}</span>
                    )}
                  </td>
                  <td style={{ fontSize: 11, color: "var(--on-variant)" }}>{record.note ?? ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
