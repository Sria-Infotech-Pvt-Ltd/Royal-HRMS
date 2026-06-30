"use client";

import { useState } from "react";
import AttendanceTab     from "./_components/AttendanceTab";
import OtEntryTab        from "./_components/OtEntryTab";
import InvalidPunchesTab from "./_components/InvalidPunchesTab";
import UnpunchesTab      from "./_components/UnpunchesTab";

type TabId = "attendance" | "ot" | "invalid" | "unpunches";

interface Tab {
  id: TabId;
  label: string;
  badge?: number;
}

const TABS: Tab[] = [
  { id: "attendance", label: "Attendance"      },
  { id: "ot",         label: "OT Entry"        },
  { id: "invalid",    label: "Invalid Punches", badge: 3 },
  { id: "unpunches",  label: "Un-punches",      badge: 7 },
];

export default function AttendancePage() {
  const [active, setActive] = useState<TabId>("attendance");

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-title">Attendance &amp; Time</div>
          <div className="page-sub">Monitor daily attendance, overtime, and correction requests</div>
        </div>
        <div className="page-actions">
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Mon, 30 Jun 2025</span>
        </div>
      </div>

      {/* Summary stat cards */}
      <div className="stats-grid mb-24">
        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Present Today</div>
              <div className="stat-value" style={{ color: "var(--success)" }}>8</div>
              <div className="stat-sub">of 12 employees</div>
            </div>
            <div className="stat-icon si-success"><i className="ti ti-user-check" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: "67%", background: "var(--success)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Absent</div>
              <div className="stat-value" style={{ color: "var(--error)" }}>2</div>
              <div className="stat-sub">No check-in recorded</div>
            </div>
            <div className="stat-icon si-error"><i className="ti ti-user-off" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: "17%", background: "var(--error)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Late Arrivals</div>
              <div className="stat-value" style={{ color: "var(--warn)" }}>2</div>
              <div className="stat-sub">Arrived after 09:15</div>
            </div>
            <div className="stat-icon si-warn"><i className="ti ti-clock-exclamation" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: "17%", background: "var(--warn)" }} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">On Leave</div>
              <div className="stat-value" style={{ color: "var(--info)" }}>2</div>
              <div className="stat-sub">Approved leave</div>
            </div>
            <div className="stat-icon si-info"><i className="ti ti-calendar-event" /></div>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: "17%", background: "var(--info)" }} />
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab${active === tab.id ? " active" : ""}`}
            onClick={() => setActive(tab.id)}
          >
            {tab.label}
            {tab.badge !== undefined && (
              <span style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                minWidth: 18, height: 18, borderRadius: 9, background: "var(--error)",
                color: "#fff", fontSize: 10, fontWeight: 700, marginLeft: 6, padding: "0 4px",
              }}>
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {active === "attendance" && <AttendanceTab />}
        {active === "ot"         && <OtEntryTab />}
        {active === "invalid"    && <InvalidPunchesTab />}
        {active === "unpunches"  && <UnpunchesTab />}
      </div>
    </div>
  );
}
