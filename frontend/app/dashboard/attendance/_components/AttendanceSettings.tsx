"use client";

import { useState } from "react";

function Toggle({ on, onChange }: { on: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      style={{
        width: 36, height: 20, borderRadius: 10, border: "none", cursor: "pointer", flexShrink: 0,
        background: on ? "var(--primary)" : "var(--outline-v)", position: "relative", transition: "background 0.15s",
      }}
    >
      <span style={{
        position: "absolute", top: 3, left: on ? 19 : 3,
        width: 14, height: 14, borderRadius: "50%", background: "#fff",
        transition: "left 0.15s", boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
      }} />
    </button>
  );
}

export default function AttendanceSettings() {
  const [absenceAlert, setAbsenceAlert] = useState(true);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Working Hours */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-clock" /> Working Hours</div>
        </div>
        <div className="card-body">
          <div className="form-row cols-4">
            <div className="field-group">
              <label className="field-label">Shift Start</label>
              <input type="time" className="field-input" defaultValue="09:00" />
            </div>
            <div className="field-group">
              <label className="field-label">Shift End</label>
              <input type="time" className="field-input" defaultValue="18:00" />
            </div>
            <div className="field-group">
              <label className="field-label">Grace Period</label>
              <select className="field-input">
                <option>15 minutes</option><option>10 minutes</option>
                <option>20 minutes</option><option>30 minutes</option>
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Break Deduction</label>
              <select className="field-input">
                <option>30 minutes (lunch)</option>
                <option>45 minutes</option><option>No deduction</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Weekly Off */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-calendar-week" /> Weekly Off Days</div>
          <span className="badge badge-error" style={{ fontSize: 10 }}>Critical</span>
        </div>
        <div className="card-body">
          <p className="field-label" style={{ marginBottom: 10 }}>Select off days — excluded from attendance calculations</p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, i) => {
              const isOff = i >= 5;
              return (
                <label key={day} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, cursor: "pointer" }}>
                  <div style={{ width: 38, height: 38, borderRadius: 7, border: `1.5px solid ${isOff ? "var(--primary)" : "var(--outline-v)"}`, background: isOff ? "var(--primary)" : "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 600, color: isOff ? "#fff" : "var(--on-variant)" }}>
                    {day}
                  </div>
                  <span style={{ fontSize: 9, color: "var(--on-variant)" }}>{day}</span>
                </label>
              );
            })}
          </div>
        </div>
      </div>

      {/* Punch Rules */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-hand-finger" /> Punch Rules</div>
        </div>
        <div className="card-body">
          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">Min Hours — Full Day</label>
              <select className="field-input"><option>8 hours</option><option>7 hours</option><option>9 hours</option></select>
            </div>
            <div className="field-group">
              <label className="field-label">Min Hours — Half Day</label>
              <select className="field-input"><option>4 hours</option><option>3.5 hours</option><option>5 hours</option></select>
            </div>
            <div className="field-group">
              <label className="field-label">Early Exit Grace</label>
              <select className="field-input"><option>30 minutes</option><option>15 minutes</option><option>45 minutes</option></select>
            </div>
          </div>
        </div>
      </div>

      {/* Overtime Rules */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-trending-up" /> Overtime Rules</div>
        </div>
        <div className="card-body">
          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">OT Threshold</label>
              <select className="field-input"><option>9 hours</option><option>8 hours</option><option>10 hours</option></select>
            </div>
            <div className="field-group">
              <label className="field-label">OT Multiplier — Regular</label>
              <select className="field-input"><option>1.5×</option><option>1.25×</option><option>2.0×</option></select>
            </div>
            <div className="field-group">
              <label className="field-label">OT Multiplier — Holiday</label>
              <select className="field-input"><option>2.0×</option><option>1.5×</option><option>2.5×</option></select>
            </div>
          </div>
        </div>
      </div>

      {/* Late Mark & LOP */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-alert-triangle" /> Late Mark &amp; LOP Rule</div>
          <span className="badge badge-error" style={{ fontSize: 10 }}>Critical</span>
        </div>
        <div className="card-body">
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Late Marks per LOP</label>
              <select className="field-input">
                <option>3 late marks = 1 LOP</option>
                <option>2 late marks = 1 LOP</option>
                <option>4 late marks = 1 LOP</option>
                <option>No LOP (tracking only)</option>
              </select>
              <span style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4, display: "block" }}>Resets each calendar month</span>
            </div>
            <div className="field-group">
              <label className="field-label">LOP Deduction Unit</label>
              <select className="field-input"><option>1 day</option><option>0.5 day (half)</option></select>
            </div>
          </div>
        </div>
      </div>

      {/* Absence Alert */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-bell" /> Absence Alert</div>
          <Toggle on={absenceAlert} onChange={() => setAbsenceAlert(v => !v)} />
        </div>
        <div className="card-body">
          <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 14 }}>
            Notify HR and the manager when an employee is absent for N+ consecutive working days without approved leave.
          </p>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Alert After N Absent Days</label>
              <select className="field-input"><option>3 days</option><option>2 days</option><option>5 days</option></select>
            </div>
            <div className="field-group">
              <label className="field-label">Notify</label>
              <select className="field-input"><option>Manager + HR</option><option>HR only</option><option>Manager only</option></select>
            </div>
          </div>
        </div>
      </div>

      {/* Save bar */}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, paddingTop: 8 }}>
        <button className="btn btn-ghost">Discard Changes</button>
        <button className="btn btn-filled">
          <i className="ti ti-device-floppy" /> Save Attendance Rules
        </button>
      </div>
    </div>
  );
}
