"use client";

import type { ApiEmployeeOption, LeaderForm } from "./_data";

export default function LeaderFields({
  label, form, setForm, employees, errors, prefix,
}: {
  label: string;
  form: LeaderForm;
  setForm: (updater: (f: LeaderForm) => LeaderForm) => void;
  employees: ApiEmployeeOption[];
  errors: Record<string, string>;
  prefix: string;
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
        <div className="field-group">
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
        <>
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
          <div className="field-group">
            <input
              type="text"
              className={`field-input${errors[`${prefix}Designation`] ? " field-error" : ""}`}
              value={form.designation}
              onChange={e => set("designation", e.target.value)}
              placeholder="Designation"
            />
            {errors[`${prefix}Designation`] && <p className="field-error-msg">{errors[`${prefix}Designation`]}</p>}
          </div>
        </>
      )}
    </div>
  );
}
