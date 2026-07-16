"use client";

import { useState } from "react";

interface Props { onNext: () => void; onBack: () => void; }

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const YEARS  = ["2024","2025","2026","2027"];

interface PeriodForm {
  month:       string;
  year:        string;
  branch:      string;
  department:  string;
  emp_type:    string;
  payroll_type: string;
  salary_date: string;
}

const BLANK: PeriodForm = {
  month: "June", year: "2026", branch: "All Branches", department: "All Departments",
  emp_type: "all", payroll_type: "regular", salary_date: "2026-06-30",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field-group">
      <label className="field-label">{label}</label>
      {children}
    </div>
  );
}

export default function PayrollPeriodStep({ onNext, onBack }: Props) {
  const [form, setForm] = useState<PeriodForm>(BLANK);
  const [errors, setErrors] = useState<Partial<PeriodForm>>({});

  function set(key: keyof PeriodForm, val: string) {
    setForm(f => ({ ...f, [key]: val }));
    setErrors(e => ({ ...e, [key]: "" }));
  }

  function validate(): boolean {
    const e: Partial<PeriodForm> = {};
    if (!form.salary_date) e.salary_date = "Salary date is required";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar" /> Payroll Period Setup</div>
        <span className="badge badge-info">Step 1 of 11</span>
      </div>
      <div className="card-body">

        <div className="alert alert-info" style={{ marginBottom: 20 }}>
          <i className="ti ti-info-circle" />
          <span>Define the payroll period and scope. All settings here apply to the entire payroll run.</span>
        </div>

        <div className="form-row cols-2">
          <Field label="Payroll Month *">
            <select className="field-input" value={form.month} onChange={e => set("month", e.target.value)}>
              {MONTHS.map(m => <option key={m}>{m}</option>)}
            </select>
          </Field>
          <Field label="Payroll Year *">
            <select className="field-input" value={form.year} onChange={e => set("year", e.target.value)}>
              {YEARS.map(y => <option key={y}>{y}</option>)}
            </select>
          </Field>
        </div>

        <div className="form-row cols-2">
          <Field label="Branch">
            <select className="field-input" value={form.branch} onChange={e => set("branch", e.target.value)}>
              <option>All Branches</option>
              <option>Head Office</option>
              <option>Mumbai</option>
              <option>Chennai</option>
              <option>Bengaluru</option>
              <option>Hyderabad</option>
            </select>
          </Field>
          <Field label="Department">
            <select className="field-input" value={form.department} onChange={e => set("department", e.target.value)}>
              <option>All Departments</option>
              <option>Engineering</option>
              <option>HR</option>
              <option>Sales</option>
              <option>Finance</option>
              <option>Operations</option>
            </select>
          </Field>
        </div>

        <div className="form-row cols-2">
          <Field label="Employee Type">
            <select className="field-input" value={form.emp_type} onChange={e => set("emp_type", e.target.value)}>
              <option value="all">All Employees</option>
              <option value="permanent">Permanent</option>
              <option value="contract">Contract</option>
              <option value="intern">Intern</option>
              <option value="probation">Probation</option>
            </select>
          </Field>
          <Field label="Payroll Type">
            <select className="field-input" value={form.payroll_type} onChange={e => set("payroll_type", e.target.value)}>
              <option value="regular">Regular Payroll</option>
              <option value="supplementary">Supplementary</option>
              <option value="advance">Advance Payroll</option>
            </select>
          </Field>
        </div>

        <div className="form-row cols-2">
          <Field label="Salary Date *">
            <input
              type="date"
              className={`field-input${errors.salary_date ? " field-error" : ""}`}
              value={form.salary_date}
              onChange={e => set("salary_date", e.target.value)}
            />
            {errors.salary_date && <span className="field-error-msg">{errors.salary_date}</span>}
          </Field>
          <div className="field-group">
            <label className="field-label">&nbsp;</label>
            <div style={{ padding: "10px 14px", background: "var(--bg-low)", borderRadius: "var(--radius)", border: "1px solid var(--outline-v)", fontSize: 13, color: "var(--on-variant)" }}>
              <i className="ti ti-users" style={{ marginRight: 6 }} />
              <strong style={{ color: "var(--on-bg)" }}>248 employees</strong> will be included in this payroll run
            </div>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8, paddingTop: 20, borderTop: "1px solid var(--outline-v)" }}>
          <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-x" /> Cancel</button>
          <button className="btn btn-filled" onClick={() => validate() && onNext()}>
            Continue <i className="ti ti-arrow-right" />
          </button>
        </div>
      </div>
    </div>
  );
}
