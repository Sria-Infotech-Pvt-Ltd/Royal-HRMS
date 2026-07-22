"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

export interface EmployeeRow {
  employee_id: string;
  employee_uuid: string;
  full_name: string;
  department: string;
  designation: string;
  present_days: number;
  late_days: number;
  half_days: number;
  absent_days: number;
  on_leave_days: number;
  lop_days: number;
  working_hours: number;
}

interface DailyRecord {
  date: string;
  day: string;
  status: string;
  status_label: string;
  working_hours: number;
  is_flagged: boolean;
}

interface DailyData {
  employee_id: string;
  full_name: string;
  days: DailyRecord[];
}

const STATUS_COLOR: Record<string, string> = {
  present:    "#15803d",
  late:       "#b45309",
  half_day:   "#1d4ed8",
  on_leave:   "#6d28d9",
  weekly_off: "var(--on-variant)",
  holiday:    "var(--on-variant)",
  absent:     "#b91c1c",
  incomplete: "#c2410c",
  no_record:  "var(--on-variant)",
};

const STATUS_BG: Record<string, string> = {
  absent:     "rgba(185,28,28,0.06)",
  incomplete: "rgba(194,65,12,0.05)",
  weekly_off: "rgba(0,0,0,0.02)",
  holiday:    "rgba(0,0,0,0.02)",
};

function fmtDate(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-IN", {
    day: "2-digit", month: "short",
  });
}

function NumCell({ value, color, bold, dim }: {
  value: number; color: string; bold?: boolean; dim?: boolean;
}) {
  return (
    <td style={{
      padding: "11px 12px", textAlign: "center", fontVariantNumeric: "tabular-nums",
      fontWeight: bold ? 700 : 500,
      color: dim ? "var(--on-variant)" : color,
      opacity: dim ? 0.35 : 1,
    }}>
      {value}
    </td>
  );
}

export default function EmployeeAttendanceRow({ emp, cycleId, cycleStart }: {
  emp: EmployeeRow;
  cycleId: string;
  cycleStart: string;
}) {
  const [expanded, setExpanded] = useState(false);

  const { data: daily, loading } = useFetch<DailyData>(
    expanded ? API.payroll.employeeDailyAttendance(cycleId, emp.employee_uuid) : null
  );

  const flaggedCount = daily?.days.filter(d => d.is_flagged).length ?? 0;

  return (
    <>
      {/* ── Summary row ─────────────────────────────────────────────────────── */}
      <tr
        onClick={() => setExpanded(e => !e)}
        style={{ cursor: "pointer", borderBottom: "1px solid var(--outline-v)" }}
      >
        <td style={{ padding: "11px 12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <i
              className={`ti ti-chevron-${expanded ? "down" : "right"}`}
              style={{ fontSize: 12, color: "var(--primary)", flexShrink: 0, transition: "transform 0.15s" }}
            />
            <div>
              <div style={{ fontWeight: 500 }}>{emp.full_name}</div>
              <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 1 }}>
                {emp.employee_id} · {emp.designation}
              </div>
            </div>
            {emp.lop_days > 0 && !expanded && (
              <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 700, color: "#b91c1c", background: "rgba(185,28,28,0.08)", padding: "1px 7px", borderRadius: 20 }}>
                {emp.lop_days} LOP
              </span>
            )}
          </div>
        </td>
        <td style={{ padding: "11px 12px", color: "var(--on-variant)", fontSize: 12 }}>{emp.department}</td>
        <NumCell value={emp.present_days}  color="#15803d" />
        <NumCell value={emp.late_days}     color="#b45309" dim={emp.late_days === 0} />
        <NumCell value={emp.half_days}     color="#1d4ed8" dim={emp.half_days === 0} />
        <NumCell value={emp.on_leave_days} color="#6d28d9" dim={emp.on_leave_days === 0} />
        <NumCell value={emp.absent_days}   color="#b91c1c" dim={emp.absent_days === 0} />
        <NumCell value={emp.lop_days}      color="#b91c1c" bold dim={emp.lop_days === 0} />
        <td style={{ padding: "11px 12px", textAlign: "center", fontVariantNumeric: "tabular-nums", color: "var(--on-variant)", fontSize: 12 }}>
          {emp.working_hours}h
        </td>
      </tr>

      {/* ── Daily breakdown panel ────────────────────────────────────────────── */}
      {expanded && (
        <tr style={{ borderBottom: "2px solid var(--primary)" }}>
          <td colSpan={9} style={{ padding: 0, background: "var(--surface, var(--bg))" }}>

            {loading ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "16px 48px", fontSize: 12, color: "var(--on-variant)" }}>
                <i className="ti ti-loader-2 animate-spin" style={{ color: "var(--primary)" }} />
                Loading daily records…
              </div>
            ) : !daily || daily.days.length === 0 ? (
              <div style={{ padding: "16px 48px", fontSize: 12, color: "var(--on-variant)" }}>
                No attendance records found for this period.
              </div>
            ) : (
              <div>
                {/* Header strip */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 48px 6px", borderBottom: "1px solid var(--outline-v)" }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--on-bg)" }}>
                    Daily Breakdown — {daily.full_name}
                    {flaggedCount > 0 && (
                      <span style={{ marginLeft: 10, fontSize: 11, color: "#b91c1c", fontWeight: 700 }}>
                        <i className="ti ti-alert-triangle" style={{ marginRight: 4 }} />
                        {flaggedCount} day{flaggedCount > 1 ? "s" : ""} flagged
                      </span>
                    )}
                  </div>
                  <a
                    href={`/dashboard/attendance?view=employee&employee=${emp.employee_uuid}&month=${cycleStart.slice(0, 7)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={e => e.stopPropagation()}
                    style={{ fontSize: 12, color: "var(--primary)", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4, fontWeight: 500 }}
                  >
                    <i className="ti ti-external-link" style={{ fontSize: 12 }} />
                    Open in Attendance Calendar
                  </a>
                </div>

                {/* Day grid */}
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr>
                        {["Date", "Day", "Status", "Hours Worked"].map(h => (
                          <th key={h} style={{
                            padding: "7px 48px 7px " + (h === "Date" ? "48px" : "12px"),
                            textAlign: h === "Hours Worked" ? "right" : "left",
                            color: "var(--on-variant)", fontWeight: 600,
                            fontSize: 11, textTransform: "uppercase", letterSpacing: ".04em",
                            borderBottom: "1px solid var(--outline-v)",
                          }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {daily.days.map(d => (
                        <tr
                          key={d.date}
                          style={{
                            background: STATUS_BG[d.status] ?? "transparent",
                            borderBottom: "1px solid var(--outline-v)",
                            opacity: d.status === "weekly_off" || d.status === "holiday" ? 0.45 : 1,
                          }}
                        >
                          <td style={{ padding: "7px 12px 7px 48px", fontVariantNumeric: "tabular-nums", color: "var(--on-bg)" }}>
                            {fmtDate(d.date)}
                          </td>
                          <td style={{ padding: "7px 12px", color: "var(--on-variant)" }}>{d.day}</td>
                          <td style={{ padding: "7px 12px" }}>
                            <span style={{
                              display: "inline-flex", alignItems: "center", gap: 5,
                              color: STATUS_COLOR[d.status] ?? "var(--on-variant)",
                              fontWeight: d.is_flagged ? 700 : 400,
                            }}>
                              {d.is_flagged && <i className="ti ti-alert-circle" style={{ fontSize: 11 }} />}
                              {d.status_label}
                            </span>
                          </td>
                          <td style={{ padding: "7px 48px 7px 12px", textAlign: "right", fontVariantNumeric: "tabular-nums", color: d.working_hours > 0 ? "var(--on-bg)" : "var(--on-variant)" }}>
                            {d.working_hours > 0 ? `${d.working_hours}h` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
