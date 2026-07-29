"use client";

import { useState } from "react";
import { useAttendanceSummary } from "@/hooks/useEmployeeDashboard";
import AssessmentLockedNotice from "./AssessmentLockedNotice";

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export default function EmpAttendanceSummary() {
  const now   = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year]            = useState(now.getFullYear());

  const { data, loading, status: httpStatus } = useAttendanceSummary(month, year);

  const stats = data ? [
    { icon: "ti-checks",        label: "Present",       val: String(data.present_days),                                color: "var(--success)"   },
    { icon: "ti-calendar-x",    label: "Absent",        val: String(data.absent_days),                                 color: "var(--error)"     },
    { icon: "ti-clock-exclamation", label: "Late Marks", val: String(data.late_marks),                                 color: "var(--warn)"      },
    { icon: "ti-beach",         label: "Leave Days",    val: String(data.leave_days),                                  color: "var(--info)"      },
    { icon: "ti-circle-half",   label: "Half Days",     val: String(data.half_days),                                   color: "var(--warn)"      },
    { icon: "ti-clock-pause",   label: "LOP Pending",   val: String(data.lop_pending),                                 color: "var(--error)"     },
    { icon: "ti-chart-pie",     label: "Attendance %",  val: `${data.attendance_percentage}%`,                         color: "var(--primary)"   },
    { icon: "ti-clock",         label: "Avg Hours/Day", val: data.avg_hours_per_day > 0 ? `${data.avg_hours_per_day.toFixed(1)}h` : "—", color: "var(--on-bg)" },
    { icon: "ti-clock-plus",    label: "OT Hours",      val: data.ot_hours || "0h",                                    color: "var(--secondary)" },
  ] : [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar-stats" /> Attendance Summary</div>
        <select
          value={month}
          onChange={e => setMonth(Number(e.target.value))}
          style={{ fontSize: 12, padding: "3px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-card)", color: "var(--on-bg)", cursor: "pointer" }}
        >
          {MONTH_NAMES.map((name, i) => (
            <option key={name} value={i + 1}>{name} {year}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : httpStatus === 403 ? (
        <AssessmentLockedNotice />
      ) : !data ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>No data for this period</div>
      ) : (
        <>
          {/* Percentage bar */}
          <div style={{ padding: "10px 20px 0" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5, fontSize: 12 }}>
              <span style={{ color: "var(--on-variant)" }}>Working days: {data.working_days}</span>
              <span style={{ fontWeight: 700, color: data.attendance_percentage >= 90 ? "var(--success)" : data.attendance_percentage >= 75 ? "var(--warn)" : "var(--error)" }}>
                {data.attendance_percentage}%
              </span>
            </div>
            <div style={{ height: 7, borderRadius: 4, background: "var(--bg-high)", overflow: "hidden" }}>
              <div style={{
                height: "100%", borderRadius: 4, transition: "width 0.4s ease",
                width: `${data.attendance_percentage}%`,
                background: data.attendance_percentage >= 90 ? "var(--success)" : data.attendance_percentage >= 75 ? "var(--warn)" : "var(--error)",
              }} />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1, padding: "12px 20px 16px" }}>
            {stats.map(stat => (
              <div key={stat.label} style={{ padding: "8px 10px", borderRadius: 8, background: "var(--bg-high)", textAlign: "center", margin: 3 }}>
                <i className={`ti ${stat.icon}`} style={{ fontSize: 15, color: stat.color, display: "block", marginBottom: 3 }} />
                <div style={{ fontSize: 15, fontWeight: 800, color: "var(--on-bg)", lineHeight: 1 }}>{stat.val}</div>
                <div style={{ fontSize: 10, color: "var(--on-variant)", marginTop: 2 }}>{stat.label}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
