"use client";

import { useState } from "react";
import RegularizationModal from "./RegularizationModal";

type HistoryStatus = "Present" | "Late" | "Absent" | "On Leave" | "Half Day" | "Weekly Off" | "Holiday";

interface HistoryRecord {
  date: string;
  day: string;
  clockIn: string;
  clockOut: string;
  hours: string;
  status: HistoryStatus;
  canRegularize: boolean;
}

const BADGE_MAP: Record<HistoryStatus, string> = {
  Present:     "badge badge-success",
  Late:        "badge badge-warn",
  Absent:      "badge badge-error",
  "On Leave":  "badge badge-info",
  "Half Day":  "badge badge-primary",
  "Weekly Off":"badge badge-neutral",
  Holiday:     "badge badge-neutral",
};

const HISTORY: HistoryRecord[] = [
  { date: "30 Jun", day: "Mon", clockIn: "09:00", clockOut: "—",     hours: "—",      status: "Present",    canRegularize: false },
  { date: "28 Jun", day: "Sat", clockIn: "—",     clockOut: "—",     hours: "—",      status: "Weekly Off", canRegularize: false },
  { date: "27 Jun", day: "Fri", clockIn: "09:42", clockOut: "18:30", hours: "8h 48m", status: "Late",       canRegularize: true  },
  { date: "26 Jun", day: "Thu", clockIn: "09:02", clockOut: "18:15", hours: "9h 13m", status: "Present",    canRegularize: false },
  { date: "25 Jun", day: "Wed", clockIn: "—",     clockOut: "—",     hours: "—",      status: "On Leave",   canRegularize: false },
  { date: "24 Jun", day: "Tue", clockIn: "08:58", clockOut: "18:05", hours: "9h 07m", status: "Present",    canRegularize: false },
  { date: "23 Jun", day: "Mon", clockIn: "09:05", clockOut: "13:10", hours: "4h 05m", status: "Half Day",   canRegularize: true  },
  { date: "20 Jun", day: "Fri", clockIn: "09:00", clockOut: "18:00", hours: "9h 00m", status: "Present",    canRegularize: false },
  { date: "19 Jun", day: "Thu", clockIn: "09:08", clockOut: "18:20", hours: "9h 12m", status: "Present",    canRegularize: false },
  { date: "18 Jun", day: "Wed", clockIn: "—",     clockOut: "—",     hours: "—",      status: "Absent",     canRegularize: true  },
];

export default function AttendanceHistory() {
  const [regularizeDate, setRegularizeDate] = useState<string | null>(null);

  function timeColor(time: string, isIn: boolean) {
    if (time === "—") return "var(--outline-v)";
    if (isIn && time > "09:15") return "var(--error)";
    return "var(--on-bg)";
  }

  return (
    <>
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <i className="ti ti-list-details" /> Attendance History — June 2025
          </div>
          <button className="btn btn-ghost btn-sm">
            <i className="ti ti-download" /> Download
          </button>
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
                <th></th>
              </tr>
            </thead>
            <tbody>
              {HISTORY.map((r, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{r.date}</td>
                  <td style={{ color: "var(--on-variant)" }}>{r.day}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: timeColor(r.clockIn, true) }}>
                    {r.clockIn}
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: timeColor(r.clockOut, false) }}>
                    {r.clockOut}
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: r.hours === "—" ? "var(--outline-v)" : "var(--on-bg)" }}>
                    {r.hours}
                  </td>
                  <td><span className={BADGE_MAP[r.status]}>{r.status}</span></td>
                  <td>
                    {r.canRegularize && (
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ padding: "3px 10px", fontSize: 11 }}
                        onClick={() => setRegularizeDate(r.date)}
                      >
                        Regularize
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {regularizeDate && (
        <RegularizationModal onClose={() => setRegularizeDate(null)} />
      )}
    </>
  );
}
