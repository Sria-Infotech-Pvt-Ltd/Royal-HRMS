"use client";

import { useApproverChoices } from "@/hooks/useApproverChoices";
import type { ApproverSelection, PersonRef } from "@/types/approvers";
import ApproverSelect from "./ApproverSelect";
import { l1Placeholder } from "./approverLabels";

interface Props {
  value: ApproverSelection;
  onChange: (next: ApproverSelection) => void;
  /** Set for an existing employee (so they are left out of their own lists); unset in the hire wizard. */
  employeeId?: string;
  errors?: Record<string, string>;
  assigned?: { reportingManager?: PersonRef | null; l1?: PersonRef | null; hr?: PersonRef | null };
  disabled?: boolean;
}

/** Reporting manager, L1 approver and L2 HR approver: shared by the hire wizard and the employee profile. */
export default function ApprovalAssignmentFields({ value, onChange, employeeId, errors = {}, assigned, disabled }: Props) {
  const choices = useApproverChoices(employeeId);
  const set = (key: keyof ApproverSelection) => (next: string) => onChange({ ...value, [key]: next });
  return (
    <>
      {choices.failed && <div className="alert alert-warn mb-16">Could not load the list of people. Try again in a moment.</div>}
      <div className="fgrid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
        <ApproverSelect
          label="Reporting manager" value={value.reporting_manager_id} onChange={set("reporting_manager_id")}
          options={choices.managers} placeholder="Follow the org chart" disabled={disabled}
          hint="Leave empty to use the head of the employee's org unit." error={errors.reporting_manager_id}
          assigned={assigned?.reportingManager}
        />
        <ApproverSelect
          label="L1 approver (leave)" value={value.l1_approver_id} onChange={set("l1_approver_id")}
          options={choices.l1} placeholder={l1Placeholder(choices.rule)} disabled={disabled}
          hint="Choose someone only if L1 should differ from what the approval rule gives."
          error={errors.l1_approver_id} assigned={assigned?.l1}
        />
        <ApproverSelect
          label="L2 HR approver" value={value.hr_id} onChange={set("hr_id")}
          options={choices.l2} placeholder="Not assigned" disabled={disabled}
          hint="The HR partner who gives the second approval." error={errors.hr_id} assigned={assigned?.hr}
        />
      </div>
    </>
  );
}
