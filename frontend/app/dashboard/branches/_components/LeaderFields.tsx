"use client";

import SearchableSelect from "@/components/SearchableSelect";
import type { ApiEmployeeOption, BranchAdminSeat, CurrentBranchAdmin, LeaderForm } from "./_data";

export default function LeaderFields({
  label, form, setForm, employees, seats, errors, prefix, currentAdmin = null,
}: {
  label: string;
  form: LeaderForm;
  setForm: (updater: (f: LeaderForm) => LeaderForm) => void;
  employees: ApiEmployeeOption[];
  seats: BranchAdminSeat[];
  errors: Record<string, string>;
  prefix: string;
  /** Edit only: who is the admin right now, shown above the fields. */
  currentAdmin?: CurrentBranchAdmin | null;
}) {
  function set<K extends keyof LeaderForm>(k: K, v: LeaderForm[K]) {
    setForm(f => ({ ...f, [k]: v }));
  }

  const filtered = form.search.trim()
    ? employees.filter(e =>
        e.full_name.toLowerCase().includes(form.search.trim().toLowerCase()) ||
        e.email.toLowerCase().includes(form.search.trim().toLowerCase()) ||
        e.employee_id.toLowerCase().includes(form.search.trim().toLowerCase()),
      )
    : employees;

  return (
    <div style={{ marginBottom: "18px" }}>
      {currentAdmin && (
        <div className="alert alert-success mb-16" style={{ alignItems: "flex-start" }}>
          <i className="ti ti-user-shield" />
          <div style={{ fontSize: 13 }}>
            <div><b>Current admin:</b> {currentAdmin.employee.full_name} ({currentAdmin.employee.employee_id})</div>
            <div>{currentAdmin.employee.email} · {currentAdmin.positionTitle}</div>
          </div>
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
        <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--primary)" }}>{label}</div>
        {employees.length > 0 && (
          <label className="module-check" style={{ fontSize: "12px", fontWeight: 400 }}>
            <input
              type="checkbox"
              checked={form.mode === "existing"}
              onChange={e => set("mode", e.target.checked ? "existing" : "new")}
            />
            <span>Assign an existing employee instead</span>
          </label>
        )}
      </div>

      {form.mode === "existing" ? (
        <div className="field-group" style={{ marginBottom: "8px" }}>
          <input
            type="text"
            className="field-input"
            value={form.search}
            onChange={e => set("search", e.target.value)}
            placeholder="Search by name, email, or employee ID…"
            style={{ marginBottom: "8px" }}
          />
          <select
            className={`field-input field-select${errors[`${prefix}Employee`] ? " field-error" : ""}`}
            value={form.employeeId}
            onChange={e => set("employeeId", e.target.value)}
          >
            <option value="">— Select employee —</option>
            {filtered.map(e => (
              <option key={e.id} value={e.id}>
                {e.full_name} ({e.employee_id}) — {e.branch || "no branch"}
              </option>
            ))}
          </select>
          {errors[`${prefix}Employee`] && <p className="field-error-msg">{errors[`${prefix}Employee`]}</p>}
        </div>
      ) : (
        <div className="form-row cols-2" style={{ marginBottom: "8px" }}>
          <div className="field-group">
            <input
              type="text"
              className={`field-input${errors[`${prefix}Name`] ? " field-error" : ""}`}
              value={form.name}
              onChange={e => set("name", e.target.value)}
              placeholder="Full name"
            />
            {errors[`${prefix}Name`] && <p className="field-error-msg">{errors[`${prefix}Name`]}</p>}
          </div>
          <div className="field-group">
            <input
              type="email"
              className={`field-input${errors[`${prefix}Email`] ? " field-error" : ""}`}
              value={form.email}
              onChange={e => set("email", e.target.value)}
              placeholder="Work email"
            />
            {errors[`${prefix}Email`] && <p className="field-error-msg">{errors[`${prefix}Email`]}</p>}
          </div>
        </div>
      )}

      {/* Both modes: the admin's access comes from the position they hold, so one is always chosen. */}
      <div className="field-group">
        <SearchableSelect
          inputClassName="field-input"
          value={form.positionId}
          onChange={v => set("positionId", v)}
          placeholder={seats.length ? "— Position with branch-wide access —" : "No position with branch-wide access yet"}
          options={seats.map(s => ({ value: s.id, label: `${s.title} — ${s.org_unit_name}${s.holder_name ? ` (held by ${s.holder_name})` : ""}` }))}
        />
        {!seats.length && (
          <div style={{ fontSize: "11px", color: "var(--on-variant)", marginTop: "4px" }}>
            <i className="ti ti-info-circle" style={{ marginRight: "4px" }} />
            No position has branch-wide access yet. Give a position that access in Org Structure first.
          </div>
        )}
        {errors[`${prefix}Position`] && <p className="field-error-msg">{errors[`${prefix}Position`]}</p>}
      </div>
    </div>
  );
}
