"use client";

import { EMPLOYMENT_TYPES } from "@/lib/employmentType";
import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import SearchableSelect from "@/components/SearchableSelect";

export interface EmploymentDraft {
  employment_type: string;
  work_email: string;
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
  // Edit record only: the Hire wizard takes these from the hire action instead.
  date_of_joining?: string;
  position?: string;
}

export const EMPTY_EMPLOYMENT: EmploymentDraft = {
  employment_type: "", work_email: "", branch: "", reporting_manager_id: "", dotted_line_manager_id: "",
  work_location: "", work_mode: "", probation_period_months: "", notice_period_days: "",
  weekly_off_policy: "", working_hours_policy: "", salary_structure: "", annual_ctc: "",
  pay_group: "monthly", attendance_scheme: "standard",
};

// In-memory cache for this step's 7 lookup calls (roles, branches, people,
// weekly-off/shift/salary-structure/leave policies) — previously these
// reloaded from scratch every single time the Employment step was
// opened/reopened within the same Hire wizard session, with no caching at
// all (QA #67). Module-level so it survives this component unmounting when
// the wizard moves to another step and remounting when the user comes back,
// but not a page reload — matches "within the wizard session", not a
// permanent cross-session cache. Mirrors the same short-TTL, session-scoped
// cache added to the shared useFetch hook for the same reason.
const EMPLOYMENT_LOOKUPS_CACHE_TTL_MS = 5 * 60 * 1000;
let employmentLookupsCache: { data: EmploymentLookups; expiresAt: number } | null = null;

interface EmploymentLookups {
  branches: { id: number; branch_name: string }[];
  people: { id: string; full_name: string; employee_id: string }[];
  weeklyPolicies: { id: string; name: string }[];
  shiftPolicies: { id: string; name: string }[];
  structures: { id: string; name: string }[];
}

const EMP_TYPES = EMPLOYMENT_TYPES;
const WORK_MODES = [["office", "Office"], ["remote", "Remote"], ["hybrid", "Hybrid"]];
const PAY_GROUPS = [["monthly", "Monthly – India"], ["weekly", "Weekly"], ["biweekly", "Bi-Weekly"], ["daily", "Daily Wage"]];
const ATTENDANCE_SCHEMES = [["standard", "Standard"], ["flexible", "Flexible"], ["shift_based", "Shift-based"]];

interface Props {
  value: EmploymentDraft;
  onChange: (next: EmploymentDraft) => void;
  onSetEmploymentType: (type: string) => void;
  reservedEmployeeId: string;
  positionTitle: string;
  orgUnitName: string;
  grade: string;
  costCenter: string;
}

export default function EmploymentStep({
  value, onChange, onSetEmploymentType, reservedEmployeeId,
  positionTitle, orgUnitName, grade, costCenter,
}: Props) {
  const [branches, setBranches] = useState<{ id: number; branch_name: string }[]>([]);
  const [people, setPeople] = useState<{ id: string; full_name: string; employee_id: string }[]>([]);
  const [weeklyPolicies, setWeeklyPolicies] = useState<{ id: string; name: string }[]>([]);
  const [shiftPolicies, setShiftPolicies] = useState<{ id: string; name: string }[]>([]);
  const [structures, setStructures] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    if (employmentLookupsCache && employmentLookupsCache.expiresAt > Date.now()) {
      const c = employmentLookupsCache.data;
      setBranches(c.branches);
      setPeople(c.people);
      setWeeklyPolicies(c.weeklyPolicies);
      setShiftPolicies(c.shiftPolicies);
      setStructures(c.structures);
      return;
    }

    Promise.allSettled([
      clientApi.get<{ data: { results: typeof branches } }>(API.employees.branches, { params: { page_size: 100 } }),
      clientApi.get<{ data: { results: typeof people } }>(API.employees.list, { params: { page_size: 200 } }),
      clientApi.get<{ data: { results: typeof weeklyPolicies } }>(API.attendance.weeklyDayPolicies, { params: { page_size: 100 } }),
      clientApi.get<{ data: { results: typeof shiftPolicies } }>(API.attendance.workingHoursPolicies, { params: { page_size: 100 } }),
      clientApi.get<{ data: { results: typeof structures } }>(API.payroll.structures, { params: { page_size: 100 } }),
    ]).then(([b, p, w, s, st]) => {
      const resolved: EmploymentLookups = {
        branches:       b.status === "fulfilled" ? (b.value.data.data.results ?? []) : [],
        people:         p.status === "fulfilled" ? (p.value.data.data.results ?? []) : [],
        weeklyPolicies: w.status === "fulfilled" ? (w.value.data.data.results ?? []) : [],
        shiftPolicies:  s.status === "fulfilled" ? (s.value.data.data.results ?? []) : [],
        structures:     st.status === "fulfilled" ? (st.value.data.data.results ?? []) : [],
      };
      setBranches(resolved.branches);
      setPeople(resolved.people);
      setWeeklyPolicies(resolved.weeklyPolicies);
      setShiftPolicies(resolved.shiftPolicies);
      setStructures(resolved.structures);

      // Only cache when every lookup actually succeeded — caching a
      // partial/failed result would keep serving empty dropdowns for the
      // next 5 minutes even after a transient failure (e.g. QA #66's
      // intermittent 503) has cleared up.
      const allFulfilled = [b, p, w, s, st].every(x => x.status === "fulfilled");
      if (allFulfilled) {
        employmentLookupsCache = {
          data: resolved,
          expiresAt: Date.now() + EMPLOYMENT_LOOKUPS_CACHE_TTL_MS,
        };
      }
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
          <select value={value.employment_type}
            onChange={e => onSetEmploymentType(e.target.value)}
            className="finput" style={{ cursor: "pointer" }}>
            <option value="">Select</option>
            {value.employment_type && !EMP_TYPES.includes(value.employment_type) && <option value={value.employment_type}>{value.employment_type}</option>}
            {EMP_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          {reservedEmployeeId && (
            <div className="hint">
              Employee number reserved: {reservedEmployeeId}. Changing this reserves a new number for the new type.
            </div>
          )}
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
          {/* .finput has a fixed height with zero vertical padding — a
              real <input>/<select> centers its text natively, but a plain
              <div> doesn't get that for free, so this text sat at the top
              of the box instead of centered. */}
          <div className="finput auto" style={{ display: "flex", alignItems: "center" }}>{positionTitle}</div>
        </div>
        <div className="f">
          <label>Org unit <span className="tag">FROM POSITION</span></label>
          <div className="finput auto" style={{ display: "flex", alignItems: "center" }}>{orgUnitName}</div>
        </div>
        <div className="f">
          <label>Grade / band <span className="tag">FROM POSITION</span></label>
          <div className="finput auto" style={{ display: "flex", alignItems: "center" }}>{grade || "—"}</div>
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
          <div className="finput auto" style={{ display: "flex", alignItems: "center" }}>{costCenter || "—"}</div>
        </div>
      </div>

      <div className="divider" />
      <div className="sechead">WORK SETUP</div>
      <div className="g3">
        <div className="f">
          <label>Company code <span className="req">*</span></label>
          <SearchableSelect value={value.branch} onChange={v => set("branch", v)}
            placeholder="Select" options={branches.map(b => ({ value: b.branch_name, label: b.branch_name }))} />
          <div className="hint">The work location is taken from the Company Code&apos;s address.</div>
        </div>
        <div className="f">
          <label>Work mode</label>
          <select value={value.work_mode} onChange={e => set("work_mode", e.target.value)} className="finput" style={{ cursor: "pointer" }}>
            <option value="">Select</option>
            {WORK_MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
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
          <label>Leave balances</label>
          <div className="finput auto" style={{ display: "flex", alignItems: "center" }}>Automatic</div>
          <div className="hint">Credited from the leave policy (Settings &gt; Leave policy) by Company Code, gender and service period.</div>
        </div>
      </div>

      <div className="divider" />
      <div className="sechead">COMPENSATION</div>
      <div className="g3">
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
