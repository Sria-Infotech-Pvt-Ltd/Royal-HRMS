"use client";

import type { HistoryRow } from "@/types/attendance";

interface Props {
  data:         HistoryRow[];
  onRegularize: (date: string) => void;
  // Hides the Regularize action — used when viewing another employee's
  // history, since the correction flow always submits against request.user.
  readOnly?:    boolean;
}

const STATUS_BADGE: Record<string, string> = {
  present:    "badge badge-success",
  late:       "badge badge-warn",
  absent:     "badge badge-error",
  half_day:   "badge badge-primary",
  weekly_off: "badge badge-neutral",
  holiday:    "badge badge-neutral",
  on_leave:   "badge badge-info",
};

const STATUS_LABEL: Record<string, string> = {
  present:    "Present",
  late:       "Late",
  absent:     "Absent",
  half_day:   "Half Day",
  weekly_off: "Weekly Off",
  holiday:    "Holiday",
  on_leave:   "On Leave",
};

export default function AttendanceHistoryTable({ data, onRegularize, readOnly = false }: Props) {
  if (data.length === 0) {
    return (
      <div className="card" style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>
        No attendance records for this month.
      </div>
    );
  }

  return (
    <div className="card">
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
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => {
              const isLateIn = row.clockIn && row.clockIn > "09:15";
              return (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{row.date}</td>
                  <td style={{ color: "var(--on-variant)" }}>{row.day}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: row.clockIn ? (isLateIn ? "var(--error)" : "var(--on-bg)") : "var(--outline-v)" }}>
                    {row.clockIn ?? "—"}
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: row.clockOut ? "var(--on-bg)" : "var(--outline-v)" }}>
                    {row.clockOut ?? "—"}
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: row.hours ? "var(--on-bg)" : "var(--outline-v)" }}>
                    {row.hours ?? "—"}
                  </td>
                  <td>
                    {STATUS_BADGE[row.status] && (
                      <span className={STATUS_BADGE[row.status]}>
                        {STATUS_LABEL[row.status] ?? row.status}
                      </span>
                    )}
                  </td>
                  <td>
                    {!readOnly && row.canRegularize && (
                      <button
                        onClick={() => onRegularize(row.date)}
                        className="btn btn-ghost btn-sm"
                        style={{ fontSize: 11, color: "var(--warn)", gap: 4 }}
                      >
                        <i className="ti ti-flag-3" style={{ fontSize: 11 }} />
                        Regularize
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
