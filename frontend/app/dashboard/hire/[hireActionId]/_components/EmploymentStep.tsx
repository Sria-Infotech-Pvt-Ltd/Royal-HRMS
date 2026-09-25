"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import SearchableSelect from "@/components/SearchableSelect";

export interface EmploymentDraft {
  employment_type: string;
  work_email: string;
  role: string;
  branch: string;
  reporting_manager_id: string;
  dotted_line_manager_id: string;
  work_location: string;
  work_mode: string;
  probation_period_months: string;
  notice_period_days: string;
  weekly_off_policy: string;
  working_hours_policy: string;
  salary_structure: string;
  annual_ctc: string;
  pay_group: string;
  attendance_scheme: string;
  leave_plan: string;
}

export const EMPTY_EMPLOYMENT: EmploymentDraft = {
  employment_type: "", work_email: "", role: "", branch: "", reporting_manager_id: "", dotted_line_manager_id: "",
  work_location: "", work_mode: "", probation_period_months: "", notice_period_days: "",
  weekly_off_policy: "", working_hours_policy: "", salary_structure: "", annual_ctc: "",
  pay_group: "monthly", attendance_scheme: "standard", leave_plan: "",
};

const EMP_TYPES = ["Permanent", "Contract", "Freelancer", "Consultant", "Part-Time", "Temporary", "Intern"];
const WORK_MODES = [["office", "Office"], ["remote", "Remote"], ["hybrid", "Hybrid"]];
const PAY_GROUPS = [["monthly", "Monthly – India"], ["weekly", "Weekly"], ["biweekly", "Bi-Weekly"], ["daily", "Daily Wage"]];
const ATTENDANCE_SCHEMES = [["standard", "Standard"], ["flexible", "Flexible"], ["shift_based", "Shift-based"]];

interface Props {
  value: EmploymentDraft;
  onChange: (next: EmploymentDraft) => void;
  onSetEmploymentType: (type: string) => void;
  employmentTypeLocked: boolean;
  positionTitle: string;
  orgUnitName: string;
  grade: string;
  costCenter: string;
  defaultRoleId: string | null;
  defaultRoleName: string | null;
}

export default function EmploymentStep({
  value, onChange, onSetEmploymentType, employmentTypeLocked,
  positionTitle, orgUnitName, grade, costCenter, defaultRoleId, defaultRoleName,
}: Props) {
  const [roles, setRoles] = useState<{ id: number; display_name: string }[]>([]);
  const [branches, setBranches] = useState<{ id: number; branch_name: string }[]>([]);
  const [people, setPeople] = useState<{ id: string; full_name: string; employee_id: string }[]>([]);
  const [weeklyPolicies, setWeeklyPolicies] = useState<{ id: string; name: string }[]>([]);
  const [shiftPolicies, setShiftPolicies] = useState<{ id: string; name: string }[]>([]);
  const [structures, setStructures] = useState<{ id: string; name: string }[]>([]);
  const [leavePolicies, setLeavePolicies] = useState<{ id: string | number; leave_type_display: string }[]>([]);

  useEffect(() => {
    Promise.allSettled([
      clientApi.get<{ data: { results: typeof roles } }>(API.roles.list, { params: { page_size: 100 } }),
      clientApi.get<{ data: { results: typeof branches } }>(API.employees.branches, { params: { page_size: 100 } }),
      clientApi.get<{ data: { results: typeof people } }>(API.employees.list, { params: { page_size: 200 } }),
      clientApi.get<{ data: { results: typeof weeklyPolicies } }>(API.attendance.weeklyDayPolicies, { params: { page_size: 100 } }),
      clientApi.get<{ data: { results: typeof shiftPolicies } }>(API.attendance.workingHoursPolicies, { params: { page_size: 100 } }),
      clientApi.get<{ data: { results: typeof structures } }>(API.payroll.structures, { params: { page_size: 100 } }),
      clientApi.get<{ data: typeof leavePolicies }>(API.leave.policy),
    ]).then(([r, b, p, w, s, st, lp]) => {
      if (r.status === "fulfilled") setRoles(r.value.data.data.results ?? []);
      if (b.status === "fulfilled") setBranches(b.value.data.data.results ?? []);
      if (p.status === "fulfilled") setPeople(p.value.data.data.results ?? []);
      if (lp.status === "fulfilled") setLeavePolicies(lp.value.data.data ?? []);
      if (w.status === "fulfilled") setWeeklyPolicies(w.value.data.data.results ?? []);
      if (s.status === "fulfilled") setShiftPolicies(s.value.data.data.results ?? []);
      if (st.status === "fulfilled") setStructures(st.value.data.data.results ?? []);
    });
  }, []);

  function set<K extends keyof EmploymentDraft>(key: K, v: EmploymentDraft[K]) {
    onChange({ ...value, [key]: v });
  }

  return (
    <div className="mstep on">
      <div className="sechead">JOB DETAILS</div>
      <div className="g3">
        <div className="f">
          <label>Work email <span className="tag">ASSIGN WHEN READY</span></label>
          <input type="email" value={value.work_email} onChange={e => set("work_email", e.target.value)} placeholder="name@company.example" className="finput" />
          <div className="hint">Separate from the personal email used for preboarding.</div>
        </div>
        <div className="f">
          <label>Employment type <span className="req">*</span></label>
          <select value={value.employment_type} disabled={employmentTypeLocked}
            onChange={e => onSetEmploymentType(e.target.value)}
            className={`finput${employmentTypeLocked ? " auto" : ""}`} style={{ cursor: employmentTypeLocked ? "not-allowed" : "pointer" }}>
            <option value="">Select</option>
            {EMP_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          {employmentTypeLocked && <div className="hint">Locked — the employee number has been reserved.</div>}
        </div>
        <div className="f">
          <label>Probation period</label>
          <select value={value.probation_period_months} onChange={e => set("probation_period_months", e.target.value)} className="finput" style={{ cursor: "pointer" }}>
            <option value="">None</option>
            {[3, 6, 12].map(m => <option key={m} value={m}>{m} months</option>)}
          </select>
        </div>
        <div className="f">
          <label>Notice period</label>
          <select value={value.notice_period_days} onChange={e => set("notice_period_days", e.target.value)} className="finput" style={{ cursor: "pointer" }}>
            <option value="">None</option>
            {[15, 30, 45, 60, 90].map(d => <option key={d} value={d}>{d} days</option>)}
          </select>
        </div>
      </div>

      <div className="divider" />
      <div className="sechead">POSITION &amp; REPORTING</div>
      <div className="g3">
        <div className="f">
          <label>Position <span className="tag">FROM ACTION</span></label>
          <div className="finput auto">{positionTitle}</div>
        </div>
        <div className="f">
          <label>Org unit <span className="tag">FROM POSITION</span></label>
          <div className="finput auto">{orgUnitName}</div>
        </div>
        <div className="f">
          <label>Grade / band <span className="tag">FROM POSITION</span></label>
          <div className="finput auto">{grade || "—"}</div>
        </div>
        <div className="f">
          <label>Reporting manager</label>
          <SearchableSelect value={value.reporting_manager_id} onChange={v => set("reporting_manager_id", v)}
            placeholder="Auto-assign" options={people.map(p => ({ value: p.id, label: p.full_name }))} />
        </div>
        <div className="f">
          <label>Dotted-line manager <span className="tag">OPTIONAL</span></label>
          <SearchableSelect value={value.dotted_line_manager_id} onChange={v => set("dotted_line_manager_id", v)}
            placeholder="None" options={people.map(p => ({ value: p.id, label: p.full_name }))} />
        </div>
        <div className="f">
          <label>Cost center <span className="tag">FROM UNIT</span></label>
          <div className="finput auto">{costCenter || "—"}</div>
        </div>
      </div>

      <div className="divider" />
      <div className="sechead">WORK SETUP</div>
      <div className="g3">
        <div className="f">
          <label>Company code <span className="req">*</span></label>
          <SearchableSelect value={value.branch} onChange={v => set("branch", v)}
            placeholder="Select" options={branches.map(b => ({ value: b.branch_name, label: b.branch_name }))} />
        </div>
        <div className="f">
          <label>Work mode</label>
          <select value={value.work_mode} onChange={e => set("work_mode", e.target.value)} className="finput" style={{ cursor: "pointer" }}>
            <option value="">Select</option>
            {WORK_MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="f">
          <label>Work location</label>
          <input value={value.work_location} onChange={e => set("work_location", e.target.value)} placeholder="e.g. Kondapur" className="finput" />
        </div>
        <div className="f">
          <label>Weekly off</label>
          <select value={value.weekly_off_policy} onChange={e => set("weekly_off_policy", e.target.value)} className="finput" style={{ cursor: "pointer" }}>
            <option value="">Company default</option>
            {weeklyPolicies.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
        <div className="f">
          <label>Shift</label>
          <select value={value.working_hours_policy} onChange={e => set("working_hours_policy", e.target.value)} className="finput" style={{ cursor: "pointer" }}>
            <option value="">Company default</option>
            {shiftPolicies.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
        <div className="f">
          <label>Pay group</label>
          <select value={value.pay_group} onChange={e => set("pay_group", e.target.value)} className="finput" style={{ cursor: "pointer" }}>
            {PAY_GROUPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="f">
          <label>Attendance scheme</label>
          <select value={value.attendance_scheme} onChange={e => set("attendance_scheme", e.target.value)} className="finput" style={{ cursor: "pointer" }}>
            {ATTENDANCE_SCHEMES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="f">
          <label>Leave plan</label>
          <SearchableSelect value={value.leave_plan} onChange={v => set("leave_plan", v)}
            placeholder="Not assigned yet" options={leavePolicies.map(p => ({ value: String(p.id), label: p.leave_type_display }))} />
        </div>
      </div>

      <div className="divider" />
      <div className="sechead">ROLE &amp; PAY</div>
      <div className="g3">
        <div className="f">
          <label>
            Role <span className="req">*</span>
            {defaultRoleId && <span className="tag">FROM POSITION</span>}
          </label>
          <SearchableSelect value={value.role} onChange={v => set("role", v)}
            placeholder="Select" options={roles.map(r => ({ value: String(r.id), label: r.display_name }))} />
          {defaultRoleId ? (
            <div className="hint">Suggested from this position&apos;s default role ({defaultRoleName}) — change it if this hire needs something different.</div>
          ) : (
            <div className="hint">This position has no default role set. Set one on the Position in Org Chart so future hires into this seat fill in automatically.</div>
          )}
        </div>
        <div className="f">
          <label>Salary structure</label>
          <SearchableSelect value={value.salary_structure} onChange={v => set("salary_structure", v)}
            placeholder="None yet" options={structures.map(s => ({ value: s.id, label: s.name }))} />
        </div>
        <div className="f">
          <label>Annual fixed CTC (₹) <span className="tag">HR</span></label>
          <input type="number" value={value.annual_ctc} onChange={e => set("annual_ctc", e.target.value)} placeholder="e.g. 800000" className="finput" />
        </div>
      </div>
    </div>
  );
}
