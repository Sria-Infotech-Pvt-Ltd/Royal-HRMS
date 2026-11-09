"use client";

import { useState } from "react";
import ApprovalAssignmentFields from "@/components/approvals/ApprovalAssignmentFields";
import { personLine } from "@/components/approvals/approverLabels";
import { useApproverAssignments } from "@/hooks/useApproverAssignments";
import { EMPTY_APPROVER_SELECTION, type ApproverAssignments, type ApproverSelection, type PersonRef } from "@/types/approvers";
import { Row, SectionCard } from "./EmployeeDrawerParts";

function selectionOf(assignments: ApproverAssignments): ApproverSelection {
  return {
    reporting_manager_id: assignments.reporting_manager.assigned?.id ?? "",
    l1_approver_id: assignments.l1_approver.assigned?.id ?? "",
    hr_id: assignments.l2_hr_approver.assigned?.id ?? "",
  };
}

const line = (person: PersonRef | null, fallback: string) => (person ? personLine(person) : fallback);

/** HR's "Approval Assignments" on an employee record: who the employee reports to and who approves their requests. */
export default function ApprovalAssignmentsSection({ employeeCode }: { employeeCode: string }) {
  const { assignments, loading, error, saving, fieldErrors, saveError, save } = useApproverAssignments(employeeCode);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ApproverSelection>(EMPTY_APPROVER_SELECTION);

  if (loading) return <SectionCard icon="ti-users" title="Approval Assignments"><Row label="Status" value="Loading…" /></SectionCard>;
  if (error || !assignments) return null;   // no permission to see approvers, or the record is outside this user's scope

  const startEditing = () => { setDraft(selectionOf(assignments)); setEditing(true); };
  const submit = async () => { if (await save(draft)) setEditing(false); };
  const { chain } = assignments;

  return (
    <SectionCard icon="ti-users" title="Approval Assignments" list={!editing}>
      {editing ? (
        <>
          <ApprovalAssignmentFields
            value={draft} onChange={setDraft} employeeId={employeeCode} errors={fieldErrors}
            assigned={{ reportingManager: assignments.reporting_manager.assigned, l1: assignments.l1_approver.assigned, hr: assignments.l2_hr_approver.assigned }}
          />
          {saveError && Object.keys(fieldErrors).length === 0 && <div className="alert alert-error" style={{ marginTop: 12 }}>{saveError}</div>}
          <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
            <button type="button" className="btn btn-filled" onClick={submit} disabled={saving}>{saving ? "Saving…" : "Save approvers"}</button>
            <button type="button" className="btn btn-ghost" onClick={() => setEditing(false)} disabled={saving}>Cancel</button>
          </div>
        </>
      ) : (
        <>
          <Row label="Reporting manager" value={line(assignments.reporting_manager.effective, "Not assigned")} />
          <Row label="L1 approver" value={chain.stages[0]?.status === "skipped" ? "Not needed (manager)" : line(assignments.l1_approver.effective, "Not assigned")} />
          <Row label="L2 HR approver" value={line(assignments.l2_hr_approver.effective, "Not assigned")} />
          {chain.warnings.map(warning => <p key={warning} style={{ margin: "6px 0 0", fontSize: 12, color: "var(--warning, #b45309)" }}>{warning}</p>)}
          {assignments.can_edit && <button type="button" className="btn btn-ghost" style={{ marginTop: 8 }} onClick={startEditing}>Edit approvers</button>}
        </>
      )}
    </SectionCard>
  );
}
