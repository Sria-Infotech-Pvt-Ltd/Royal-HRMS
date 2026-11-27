"use client";

import type { AssignmentAction, WorkStatusAssignment } from "@/types/workStatus";
import { endLabel, fmtDate, statusBadge, statusLabel, workPlaceLabel } from "./workStatusFormat";

interface Props {
  assignment: WorkStatusAssignment;
  /** Present only for admins who may change the assignment. */
  onAction?:  (action: AssignmentAction, assignment: WorkStatusAssignment) => void;
}

// One current project in the Work Status panel. When it ends soon, admins are prompted to extend it or assign the next one.
export default function CurrentAssignmentCard({ assignment, onAction }: Props) {
  const isWarning = assignment.is_ending_soon;
  return (
    <div style={{
      border: `1px solid ${isWarning ? "var(--warn)" : "var(--border)"}`, borderRadius: 8,
      padding: "10px 14px", marginBottom: 8,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{assignment.project_name}</div>
        <span className={statusBadge(assignment)} style={{ fontSize: 10 }}>{statusLabel(assignment)}</span>
      </div>
      <div style={{ fontSize: 12, marginTop: 4 }}>
        {fmtDate(assignment.start_date)} – {endLabel(assignment)}
        {assignment.role && <span style={{ color: "var(--on-variant)" }}> · {assignment.role}</span>}
      </div>
      <div style={{ fontSize: 12, marginTop: 4 }}>
        <i className="ti ti-map-pin" style={{ color: "var(--on-variant)" }} /> {workPlaceLabel(assignment)}
      </div>
      {assignment.notes && <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>{assignment.notes}</div>}
      {onAction && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          <button className={`btn btn-sm ${isWarning ? "btn-filled" : "btn-outline"}`} type="button" onClick={() => onAction("extend", assignment)}>
            <i className="ti ti-calendar-plus" /> Extend
          </button>
          <button className="btn btn-outline btn-sm" type="button" onClick={() => onAction("edit", assignment)}>
            <i className="ti ti-pencil" /> Edit
          </button>
          <button className="btn btn-outline btn-sm" type="button" onClick={() => onAction("end", assignment)}>
            <i className="ti ti-flag" /> End
          </button>
          {isWarning && (
            <button className="btn btn-outline btn-sm" type="button" onClick={() => onAction("assign", assignment)}>
              <i className="ti ti-plus" /> Assign new project
            </button>
          )}
        </div>
      )}
    </div>
  );
}
