"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { MultiCheckRow, type PolicyRuleFields } from "./LeavePoliciesTab";
import type { DepartmentOption } from "@/types/department";
import type { DesignationOption } from "@/types/designation";

interface BranchOption      { id: number; branch_name: string }

// No employment-type concept exists anywhere in this system yet (checked
// accounts.models — no field, no choices). Kept as a static placeholder list
// matching the exact values the backend's PUT example uses ("Full-time",
// "Part-time") until a real backend enum exists to source it from.
const EMPLOYMENT_TYPE_OPTIONS = ["Full-time", "Part-time", "Contract", "Intern", "Consultant"];

// Exactly the three values the backend accepts — confirmed from the field
// reference table (all / male / female, no "other").
const GENDER_OPTIONS: { value: string; label: string }[] = [
  { value: "all",    label: "All" },
  { value: "male",   label: "Male" },
  { value: "female", label: "Female" },
];

// The four checkbox-group fields this section's single "Select All" toggle
// controls together — Gender and Minimum Service Period are not checkbox
// groups, so they're excluded.
type EligibilityListKey =
  | "applicable_branches"
  | "applicable_departments"
  | "applicable_designations"
  | "applicable_employment_types";

interface Props {
  rules: PolicyRuleFields;
  setField: <K extends keyof PolicyRuleFields>(key: K, value: PolicyRuleFields[K]) => void;
}

export default function EligibilitySection({ rules, setField }: Props) {
  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(`${API.branches.list}?page_size=100`);
  const { data: deptData }   = useFetch<DepartmentOption[] | { results: DepartmentOption[] }>(API.departments.list);
  const { data: desigData }  = useFetch<DesignationOption[] | { results: DesignationOption[] }>(API.designations.list);

  const branches     = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);
  const departments  = Array.isArray(deptData)   ? deptData   : (deptData?.results ?? []);
  const designations = Array.isArray(desigData)  ? desigData  : (desigData?.results ?? []);

  const groups: { key: EligibilityListKey; options: string[] }[] = [
    { key: "applicable_branches",         options: branches.map(b => b.branch_name) },
    { key: "applicable_departments",      options: departments.map(d => d.name) },
    { key: "applicable_designations",     options: designations.map(d => d.name) },
    { key: "applicable_employment_types", options: EMPLOYMENT_TYPE_OPTIONS },
  ];
  const eligibleGroups = groups.filter(g => g.options.length > 0);
  const allSelected = eligibleGroups.length > 0 && eligibleGroups.every(g => rules[g.key].length === g.options.length);
  const anySelected = eligibleGroups.some(g => rules[g.key].length > 0);
  const isPartial   = anySelected && !allSelected;

  function toggleAllGroups(checked: boolean) {
    // Checked → mark every branch/department/designation/employment type
    // explicitly, so the admin can then uncheck just the ones this leave
    // type should NOT apply to. Unchecked → clear all back to [], which the
    // backend treats as "no restriction" (applies to all).
    groups.forEach(g => setField(g.key, checked ? [...g.options] : []));
  }

  return (
    <div className="card mb-20">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-users-group" /> Eligibility Rules</div>
        <label className="module-check text-xs">
          <input
            type="checkbox"
            checked={allSelected}
            disabled={eligibleGroups.length === 0}
            ref={el => { if (el) el.indeterminate = isPartial; }}
            onChange={e => toggleAllGroups(e.target.checked)}
          />
          <span>Select All</span>
        </label>
      </div>
      <div style={{ padding: "20px 24px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
          <MultiCheckRow
            label="Applicable Branches"
            options={branches.map(b => b.branch_name)}
            selected={rules.applicable_branches}
            onChange={v => setField("applicable_branches", v)}
          />
          <MultiCheckRow
            label="Departments"
            options={departments.map(d => d.name)}
            selected={rules.applicable_departments}
            onChange={v => setField("applicable_departments", v)}
          />
          <MultiCheckRow
            label="Designations"
            options={designations.map(d => d.name)}
            selected={rules.applicable_designations}
            onChange={v => setField("applicable_designations", v)}
          />
          <MultiCheckRow
            label="Employment Types"
            options={EMPLOYMENT_TYPE_OPTIONS}
            selected={rules.applicable_employment_types}
            onChange={v => setField("applicable_employment_types", v)}
          />
          <div className="field-group mb-16">
            <label className="field-label">Gender</label>
            <select className="field-input" value={rules.applicable_gender} onChange={e => setField("applicable_gender", e.target.value)}>
              {GENDER_OPTIONS.map(g => <option key={g.value} value={g.value}>{g.label}</option>)}
            </select>
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Minimum Service Period (months)</label>
            <input className="field-input" type="number" min={0} value={rules.minimum_service_period} onChange={e => setField("minimum_service_period", Number(e.target.value))} />
          </div>
        </div>
      </div>
    </div>
  );
}
