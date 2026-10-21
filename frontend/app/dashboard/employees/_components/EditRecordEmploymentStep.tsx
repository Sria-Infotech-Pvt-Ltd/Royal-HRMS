"use client";

// Edit record > Employment — the reference layout: JOB DETAILS / POSITION & REPORTING / WORK SETUP / COMPENSATION.
// Org unit and grade follow the chosen position. Weekly off, shift, attendance scheme, leave plan, salary
// structure and work email have no post-hire write path yet (see the note at the top of EditRecordModal.tsx):
// they render and can be changed here but are not sent on save.

import { useMemo } from "react";
import DateInput from "@/components/shared/DateInput";
import type { EmploymentDraft } from "../../hire/[hireActionId]/_components/EmploymentStep";
import { useEmploymentLookups } from "@/hooks/useEmploymentLookups";

const EMPLOYMENT_TYPES = ["Permanent", "Contract", "Freelancer", "Consultant", "Part-Time", "Temporary", "Intern"];
const WORK_MODES: [string, string][] = [["office", "Office"], ["hybrid", "Hybrid"], ["remote", "Remote"]];
const ATTENDANCE_SCHEMES: [string, string][] = [["standard", "Standard – Office"], ["flexible", "Flexible"], ["shift_based", "Shift-based"]];
const PROBATION_MONTHS = [3, 6, 12];
const NOTICE_DAYS = [15, 30, 45, 60, 90];

interface Props {
  value: EmploymentDraft;
  onChange: (next: EmploymentDraft) => void;
  positionTitle: string;
  orgUnitName: string;
}

function addMonthsIso(isoDate: string, months: number): string {
  if (!isoDate || !months) return "";
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1 + months, day)).toISOString().slice(0, 10);
}

function Required() { return <span className="req">*</span>; }
function Tag({ text }: { text: string }) { return <span className="tag">{text}</span>; }

export default function EditRecordEmploymentStep({ value, onChange, positionTitle, orgUnitName }: Props) {
  const lookups = useEmploymentLookups();
  const set = <K extends keyof EmploymentDraft>(key: K, next: EmploymentDraft[K]) => onChange({ ...value, [key]: next });

  // The employee's current seat, until a different position is picked.
  const currentPositionId = useMemo(
    () => lookups.positions.find(p => p.title === positionTitle && p.org_unit_name === orgUnitName)?.id ?? "",
    [lookups.positions, positionTitle, orgUnitName],
  );
  const selectedPositionId = value.position || currentPositionId;
  const selectedPosition = lookups.positions.find(p => p.id === selectedPositionId);
  const unitName = selectedPosition?.org_unit_name ?? orgUnitName;
  const band = selectedPosition ? [selectedPosition.grade, selectedPosition.job_template_name].filter(Boolean).join(" · ") : "";

  const workLocations = useMemo(() => {
    const names = new Set(lookups.people.map(p => p.work_location?.trim()).filter((name): name is string => !!name));
    if (value.work_location) names.add(value.work_location);
    return [...names].sort();
  }, [lookups.people, value.work_location]);

  const confirmationDate = addMonthsIso(value.date_of_joining ?? "", Number(value.probation_period_months) || 0);

  return (
    <div className="mstep on">
      <div className="sechead">JOB DETAILS</div>
      <div className="g3">
        <div className="f"><label>Date of joining <Required /></label>
          <DateInput className="finput" value={value.date_of_joining ?? ""} onChange={iso => set("date_of_joining", iso)} /></div>
        <div className="f"><label>Work email <Tag text="ASSIGN WHEN READY" /></label>
          <input type="email" className="finput" value={value.work_email} onChange={e => set("work_email", e.target.value)} placeholder="name@company.example" />
          <div className="hint">Separate from the personal email used for preboarding.</div></div>
        <div className="f"><label>Employment type <Required /></label>
          <select className="finput" value={value.employment_type} onChange={e => set("employment_type", e.target.value)}>
            <option value="">Select</option>
            {EMPLOYMENT_TYPES.map(type => <option key={type} value={type}>{type}</option>)}
          </select></div>
        <div className="f"><label>Probation period</label>
          <select className="finput" value={value.probation_period_months} onChange={e => set("probation_period_months", e.target.value)}>
            <option value="">None</option>
            {PROBATION_MONTHS.map(months => <option key={months} value={months}>{months} months</option>)}
          </select></div>
        <div className="f"><label>Confirmation date <Tag text="AUTO" /></label>
          <DateInput className="finput auto" readOnly value={confirmationDate} onChange={() => {}} /></div>
        <div className="f"><label>Notice period</label>
          <select className="finput" value={value.notice_period_days} onChange={e => set("notice_period_days", e.target.value)}>
            <option value="">None</option>
            {NOTICE_DAYS.map(days => <option key={days} value={days}>{days} days</option>)}
          </select></div>
      </div>

      <div className="divider" />
      <div className="sechead">POSITION &amp; REPORTING</div>
      <div className="g3">
        <div className="f"><label>Position <Required /></label>
          <select className="finput" value={selectedPositionId} onChange={e => set("position", e.target.value)}>
            {!selectedPositionId && <option value="">{positionTitle || "Select a position"}</option>}
            {lookups.positions.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select></div>
        <div className="f"><label>Org unit <Tag text="FROM POSITION" /></label>
          <input className="finput auto" disabled value={unitName} placeholder="Set by position" /></div>
        <div className="f"><label>Grade / band <Tag text="FROM POSITION" /></label>
          <input className="finput auto" disabled value={band} placeholder="Set by position" /></div>
        <div className="f"><label>Reporting manager <Required /> <Tag text="FROM UNIT" /></label>
          <select className="finput" value={value.reporting_manager_id} onChange={e => set("reporting_manager_id", e.target.value)}>
            <option value="">Assign later</option>
            {lookups.people.map(p => <option key={p.id} value={p.id}>{p.full_name}</option>)}
          </select>
          {!value.reporting_manager_id && (
            <div className="hint" style={{ color: "var(--crit)", fontWeight: 600 }}>
              No manager mapped to {unitName || "this unit"} — assign later and HR will set it.
            </div>
          )}</div>
        <div className="f"><label>Dotted-line manager <Tag text="OPTIONAL" /></label>
          <select className="finput" value={value.dotted_line_manager_id} onChange={e => set("dotted_line_manager_id", e.target.value)}>
            <option value="">None</option>
            {lookups.people.map(p => <option key={p.id} value={p.id}>{p.full_name}</option>)}
          </select>
          <div className="hint">Any unit — cross-functional reporting.</div></div>
        <div className="f"><label>Cost center <Tag text="FROM UNIT" /></label>
          <input className="finput auto" disabled value="" placeholder="Set by position" /></div>
      </div>

      <div className="divider" />
      <div className="sechead">WORK SETUP</div>
      <div className="g3">
        <div className="f"><label>Work location <Required /></label>
          <select className="finput" value={value.work_location} onChange={e => set("work_location", e.target.value)}>
            <option value="">Select</option>
            {workLocations.map(name => <option key={name} value={name}>{name}</option>)}
          </select></div>
        <div className="f"><label>Work mode</label>
          <select className="finput" value={value.work_mode} onChange={e => set("work_mode", e.target.value)}>
            <option value="">Select</option>
            {WORK_MODES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></div>
        <div className="f"><label>Shift</label>
          <select className="finput" value={value.working_hours_policy} onChange={e => set("working_hours_policy", e.target.value)}>
            <option value="">Company default</option>
            {lookups.shiftPolicies.map(policy => <option key={policy.id} value={policy.id}>{policy.name}</option>)}
          </select></div>
        <div className="f"><label>Weekly off</label>
          <select className="finput" value={value.weekly_off_policy} onChange={e => set("weekly_off_policy", e.target.value)}>
            <option value="">Company default</option>
            {lookups.weeklyPolicies.map(policy => <option key={policy.id} value={policy.id}>{policy.name}</option>)}
          </select></div>
        <div className="f"><label>Attendance scheme <Required /></label>
          <select className="finput" value={value.attendance_scheme} onChange={e => set("attendance_scheme", e.target.value)}>
            {ATTENDANCE_SCHEMES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></div>
        <div className="f"><label>Leave plan <Required /></label>
          <select className="finput" value={value.leave_plan} onChange={e => set("leave_plan", e.target.value)}>
            <option value="">Select</option>
            {lookups.leavePolicies.map(policy => <option key={policy.id} value={String(policy.id)}>{policy.leave_type_display}</option>)}
          </select></div>
      </div>

      <div className="divider" />
      <div className="sechead">COMPENSATION</div>
      <div className="g3">
        <div className="f"><label>Pay group</label>
          <input className="finput auto" disabled value="Monthly – India" /></div>
        <div className="f"><label>Salary structure <Tag text="OPTIONAL" /></label>
          <select className="finput" value={value.salary_structure} onChange={e => set("salary_structure", e.target.value)}>
            <option value="">Not assigned</option>
            {lookups.structures.map(structure => <option key={structure.id} value={structure.id}>{structure.name}</option>)}
          </select></div>
        <div className="f"><label>Annual fixed CTC <span className="own hr">HR</span></label>
          <div className="prefix"><span>₹</span>
            <input type="number" className="finput" min={0} max={100000000} step={1000} value={value.annual_ctc}
              onChange={e => set("annual_ctc", e.target.value)} placeholder="800000" /></div>
          <div className="hint">Total fixed cost to company per year, excluding variable pay and bonus.</div></div>
      </div>
    </div>
  );
}
