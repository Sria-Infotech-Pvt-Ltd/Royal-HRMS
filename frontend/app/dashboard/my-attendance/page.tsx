"use client";

import ClockWidget    from "./_components/ClockWidget";
import MyCalendarTab  from "./_components/MyCalendarTab";

export default function MyAttendancePage() {
  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-title">My Attendance</div>
          <div className="page-sub">Clock in/out and view your personal attendance calendar</div>
        </div>
        <div className="page-actions">
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Mon, 30 Jun 2025</span>
        </div>
      </div>

      {/* Stat cards */}
      <div className="stats-grid mb-24">
        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Days Present</div>
              <div className="stat-value">22</div>
              <div className="stat-sub">This month</div>
            </div>
            <div className="stat-icon si-success"><i className="ti ti-user-check" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: "88%", background: "var(--success)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Late Arrivals</div>
              <div className="stat-value" style={{ color: "var(--warn)" }}>3</div>
              <div className="stat-sub">1 LOP pending</div>
            </div>
            <div className="stat-icon si-warn"><i className="ti ti-clock-exclamation" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: "12%", background: "var(--warn)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Avg Hours / Day</div>
              <div className="stat-value">8.4</div>
              <div className="stat-sub">Required: 9.0 hrs</div>
            </div>
            <div className="stat-icon si-info"><i className="ti ti-clock" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: "93%", background: "var(--info)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Attendance %</div>
              <div className="stat-value" style={{ color: "var(--success)" }}>96%</div>
              <div className="stat-sub">Above threshold</div>
            </div>
            <div className="stat-icon si-success"><i className="ti ti-chart-bar" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: "96%", background: "var(--success)" }} />
          </div>
        </div>
      </div>

      {/* Top row: clock widget + monthly summary side by side */}
      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 16, alignItems: "start", marginBottom: 16 }}>

        <ClockWidget />

        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-calendar-stats" /> Monthly Summary</div>
          </div>
          <div className="card-body">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0 }}>
              {[
                { label: "Working Days", value: "25", color: "var(--on-bg)"   },
                { label: "Days Present", value: "22", color: "var(--success)" },
                { label: "Days Absent",  value: "1",  color: "var(--error)"   },
                { label: "Leave Days",   value: "1",  color: "var(--info)"    },
                { label: "Half Days",    value: "1",  color: "var(--primary)" },
                { label: "OT Hours",     value: "2h", color: "var(--success)" },
              ].map((item, idx) => (
                <div key={item.label} style={{ padding: "14px 16px", borderBottom: idx < 3 ? "1px solid var(--outline-v)" : "none", borderRight: idx % 3 !== 2 ? "1px solid var(--outline-v)" : "none" }}>
                  <div style={{ fontSize: 11, color: "var(--on-variant)", marginBottom: 6 }}>{item.label}</div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: item.color, fontVariantNumeric: "tabular-nums" }}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Full-width calendar below */}
      <MyCalendarTab />
    </div>
  );
}
