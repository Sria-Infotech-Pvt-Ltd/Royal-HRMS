"use client";

import { useAttendanceSettings } from "@/hooks/useAttendanceSettings";
import type { AttendanceSettingsForm, WeeklyOffSection } from "@/types/attendanceSettings";

// ─── Constants ────────────────────────────────────────────────────────────────

const DAYS: Array<{ label: string; key: keyof WeeklyOffSection }> = [
  { label: "Mon", key: "monday"    },
  { label: "Tue", key: "tuesday"   },
  { label: "Wed", key: "wednesday" },
  { label: "Thu", key: "thursday"  },
  { label: "Fri", key: "friday"    },
  { label: "Sat", key: "saturday"  },
  { label: "Sun", key: "sunday"    },
];

// ─── Sub-components ───────────────────────────────────────────────────────────

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

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function AttendanceSettings() {
  const {
    form, setForm,
    loading, error,
    saving, savingSection,
    fieldErrors,
    save, saveSection, reset,
  } = useAttendanceSettings();

  const isBusy = saving || savingSection !== null;

  // Field-level error helpers
  const fe = fieldErrors;
  const errStyle = (s: string, f: string) =>
    fe[s]?.[f]?.length ? { borderColor: "var(--error)" } : undefined;
  const fieldErr = (s: string, f: string) => fe[s]?.[f]?.[0];

  // Section save button (PATCH)
  function SectionSave({ section }: { section: keyof AttendanceSettingsForm }) {
    return (
      <button
        className="btn btn-ghost"
        style={{ height: 28, fontSize: 12, padding: "0 12px" }}
        onClick={() => saveSection(section)}
        disabled={isBusy}
      >
        {savingSection === section
          ? <><Spin />&nbsp;Saving…</>
          : <><i className="ti ti-device-floppy" />&nbsp;Save</>}
      </button>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Loading / error banner */}
      {loading && (
        <div style={{ textAlign: "center", padding: "12px 0", color: "var(--on-variant)", fontSize: 13 }}>
          <Spin /> Loading settings…
        </div>
      )}
      {error && !loading && (
        <p style={{ color: "var(--error)", fontSize: 12, margin: 0 }}>
          <i className="ti ti-alert-circle" style={{ marginRight: 4 }} />{error}
        </p>
      )}

      {/* Working Hours */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-clock" /> Working Hours</div>
          <SectionSave section="working_hours" />
        </div>
        <div className="card-body">
          <div className="form-row cols-4">
            <div className="field-group">
              <label className="field-label">Shift Start</label>
              <input type="time" className="field-input" style={errStyle("working_hours", "shift_start")}
                value={form.working_hours.shift_start}
                onChange={e => setForm(f => ({ ...f, working_hours: { ...f.working_hours, shift_start: e.target.value } }))}
              />
              {fieldErr("working_hours", "shift_start") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("working_hours", "shift_start")}</span>}
            </div>
            <div className="field-group">
              <label className="field-label">Shift End</label>
              <input type="time" className="field-input" style={errStyle("working_hours", "shift_end")}
                value={form.working_hours.shift_end}
                onChange={e => setForm(f => ({ ...f, working_hours: { ...f.working_hours, shift_end: e.target.value } }))}
              />
              {fieldErr("working_hours", "shift_end") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("working_hours", "shift_end")}</span>}
            </div>
            <div className="field-group">
              <label className="field-label">Grace Period (min)</label>
              <input type="number" className="field-input" min={0} max={120} style={errStyle("working_hours", "grace_period_minutes")}
                value={form.working_hours.grace_period_minutes}
                onChange={e => setForm(f => ({ ...f, working_hours: { ...f.working_hours, grace_period_minutes: Number(e.target.value) } }))}
              />
              {fieldErr("working_hours", "grace_period_minutes") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("working_hours", "grace_period_minutes")}</span>}
            </div>
            <div className="field-group">
              <label className="field-label">Break Duration (min)</label>
              <input type="number" className="field-input" min={0} max={480} style={errStyle("working_hours", "break_duration_minutes")}
                value={form.working_hours.break_duration_minutes}
                onChange={e => setForm(f => ({ ...f, working_hours: { ...f.working_hours, break_duration_minutes: Number(e.target.value) } }))}
              />
              {fieldErr("working_hours", "break_duration_minutes") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("working_hours", "break_duration_minutes")}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Weekly Off */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-calendar-week" /> Weekly Off Days</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="badge badge-error" style={{ fontSize: 10 }}>Critical</span>
            <SectionSave section="weekly_off" />
          </div>
        </div>
        <div className="card-body">
          <p className="field-label" style={{ marginBottom: 10 }}>Select off days — excluded from attendance calculations</p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {DAYS.map(({ label, key }) => {
              const isOff = form.weekly_off[key];
              return (
                <label key={key} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, cursor: "pointer" }}
                  onClick={() => setForm(f => ({ ...f, weekly_off: { ...f.weekly_off, [key]: !f.weekly_off[key] } }))}
                >
                  <div style={{ width: 38, height: 38, borderRadius: 7, border: `1.5px solid ${isOff ? "var(--primary)" : "var(--outline-v)"}`, background: isOff ? "var(--primary)" : "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 600, color: isOff ? "#fff" : "var(--on-variant)" }}>
                    {label}
                  </div>
                  <span style={{ fontSize: 9, color: "var(--on-variant)" }}>{label}</span>
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
          <SectionSave section="punch_rules" />
        </div>
        <div className="card-body">
          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">Min Hours — Full Day</label>
              <select className="field-input" style={errStyle("punch_rules", "min_hours_full_day")}
                value={form.punch_rules.min_hours_full_day}
                onChange={e => setForm(f => ({ ...f, punch_rules: { ...f.punch_rules, min_hours_full_day: e.target.value } }))}
              >
                <option value="8.00">8 hours</option>
                <option value="7.00">7 hours</option>
                <option value="9.00">9 hours</option>
              </select>
              {fieldErr("punch_rules", "min_hours_full_day") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("punch_rules", "min_hours_full_day")}</span>}
            </div>
            <div className="field-group">
              <label className="field-label">Min Hours — Half Day</label>
              <select className="field-input" style={errStyle("punch_rules", "min_hours_half_day")}
                value={form.punch_rules.min_hours_half_day}
                onChange={e => setForm(f => ({ ...f, punch_rules: { ...f.punch_rules, min_hours_half_day: e.target.value } }))}
              >
                <option value="4.00">4 hours</option>
                <option value="3.50">3.5 hours</option>
                <option value="5.00">5 hours</option>
              </select>
              {fieldErr("punch_rules", "min_hours_half_day") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("punch_rules", "min_hours_half_day")}</span>}
            </div>
            <div className="field-group">
              <label className="field-label">Early Exit Grace</label>
              <select className="field-input" style={errStyle("punch_rules", "early_exit_grace_minutes")}
                value={form.punch_rules.early_exit_grace_minutes}
                onChange={e => setForm(f => ({ ...f, punch_rules: { ...f.punch_rules, early_exit_grace_minutes: Number(e.target.value) } }))}
              >
                <option value={30}>30 minutes</option>
                <option value={15}>15 minutes</option>
                <option value={45}>45 minutes</option>
              </select>
              {fieldErr("punch_rules", "early_exit_grace_minutes") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("punch_rules", "early_exit_grace_minutes")}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Overtime Rules */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-trending-up" /> Overtime Rules</div>
          <SectionSave section="overtime_rules" />
        </div>
        <div className="card-body">
          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">OT Threshold</label>
              <select className="field-input" style={errStyle("overtime_rules", "ot_threshold_hours")}
                value={form.overtime_rules.ot_threshold_hours}
                onChange={e => setForm(f => ({ ...f, overtime_rules: { ...f.overtime_rules, ot_threshold_hours: e.target.value } }))}
              >
                <option value="9.00">9 hours</option>
                <option value="8.00">8 hours</option>
                <option value="10.00">10 hours</option>
              </select>
              {fieldErr("overtime_rules", "ot_threshold_hours") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("overtime_rules", "ot_threshold_hours")}</span>}
            </div>
            <div className="field-group">
              <label className="field-label">OT Multiplier — Regular</label>
              <select className="field-input" style={errStyle("overtime_rules", "ot_multiplier_regular")}
                value={form.overtime_rules.ot_multiplier_regular}
                onChange={e => setForm(f => ({ ...f, overtime_rules: { ...f.overtime_rules, ot_multiplier_regular: e.target.value } }))}
              >
                <option value="1.50">1.5×</option>
                <option value="1.25">1.25×</option>
                <option value="2.00">2.0×</option>
              </select>
              {fieldErr("overtime_rules", "ot_multiplier_regular") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("overtime_rules", "ot_multiplier_regular")}</span>}
            </div>
            <div className="field-group">
              <label className="field-label">OT Multiplier — Holiday</label>
              <select className="field-input" style={errStyle("overtime_rules", "ot_multiplier_holiday")}
                value={form.overtime_rules.ot_multiplier_holiday}
                onChange={e => setForm(f => ({ ...f, overtime_rules: { ...f.overtime_rules, ot_multiplier_holiday: e.target.value } }))}
              >
                <option value="2.00">2.0×</option>
                <option value="1.50">1.5×</option>
                <option value="2.50">2.5×</option>
              </select>
              {fieldErr("overtime_rules", "ot_multiplier_holiday") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("overtime_rules", "ot_multiplier_holiday")}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Late Mark & LOP */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-alert-triangle" /> Late Mark &amp; LOP Rule</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="badge badge-error" style={{ fontSize: 10 }}>Critical</span>
            <SectionSave section="late_mark_rules" />
          </div>
        </div>
        <div className="card-body">
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Late Marks per LOP</label>
              <select className="field-input" style={errStyle("late_mark_rules", "late_marks_per_lop")}
                value={form.late_mark_rules.late_marks_per_lop}
                onChange={e => setForm(f => ({ ...f, late_mark_rules: { ...f.late_mark_rules, late_marks_per_lop: Number(e.target.value) } }))}
              >
                <option value={3}>3 late marks = 1 LOP</option>
                <option value={2}>2 late marks = 1 LOP</option>
                <option value={4}>4 late marks = 1 LOP</option>
                <option value={0}>No LOP (tracking only)</option>
              </select>
              <span style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4, display: "block" }}>Resets each calendar month</span>
              {fieldErr("late_mark_rules", "late_marks_per_lop") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("late_mark_rules", "late_marks_per_lop")}</span>}
            </div>
            <div className="field-group">
              <label className="field-label">LOP Deduction Unit</label>
              <select className="field-input" style={errStyle("late_mark_rules", "lop_deduction_unit")}
                value={form.late_mark_rules.lop_deduction_unit}
                onChange={e => setForm(f => ({ ...f, late_mark_rules: { ...f.late_mark_rules, lop_deduction_unit: e.target.value } }))}
              >
                <option value="full_day">1 day</option>
                <option value="half_day">0.5 day (half)</option>
              </select>
              {fieldErr("late_mark_rules", "lop_deduction_unit") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("late_mark_rules", "lop_deduction_unit")}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Absence Alert */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-bell" /> Absence Alert</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <SectionSave section="absence_alert" />
            <Toggle
              on={form.absence_alert.is_enabled}
              onChange={() => setForm(f => ({ ...f, absence_alert: { ...f.absence_alert, is_enabled: !f.absence_alert.is_enabled } }))}
            />
          </div>
        </div>
        <div className="card-body">
          <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 14 }}>
            Notify HR and the manager when an employee is absent for N+ consecutive working days without approved leave.
          </p>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Alert After N Absent Days</label>
              <select className="field-input" style={errStyle("absence_alert", "alert_after_days")}
                value={form.absence_alert.alert_after_days}
                onChange={e => setForm(f => ({ ...f, absence_alert: { ...f.absence_alert, alert_after_days: Number(e.target.value) } }))}
              >
                <option value={3}>3 days</option>
                <option value={2}>2 days</option>
                <option value={5}>5 days</option>
              </select>
              {fieldErr("absence_alert", "alert_after_days") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("absence_alert", "alert_after_days")}</span>}
            </div>
            <div className="field-group">
              <label className="field-label">Notify</label>
              <select className="field-input" style={errStyle("absence_alert", "notify_whom")}
                value={form.absence_alert.notify_whom}
                onChange={e => setForm(f => ({ ...f, absence_alert: { ...f.absence_alert, notify_whom: e.target.value } }))}
              >
                <option value="manager_and_hr">Manager + HR</option>
                <option value="hr_only">HR only</option>
                <option value="manager_only">Manager only</option>
              </select>
              {fieldErr("absence_alert", "notify_whom") && <span style={{ fontSize: 11, color: "var(--error)", marginTop: 4, display: "block" }}>{fieldErr("absence_alert", "notify_whom")}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Save bar */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, paddingTop: 8 }}>
        <button className="btn btn-ghost" onClick={reset} disabled={isBusy}>Discard Changes</button>
        <button className="btn btn-filled" onClick={save} disabled={isBusy || loading}>
          {saving
            ? <><Spin />&nbsp;Saving…</>
            : <><i className="ti ti-device-floppy" /> Save All</>}
        </button>
      </div>

    </div>
  );
}
