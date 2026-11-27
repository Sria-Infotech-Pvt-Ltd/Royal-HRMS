"use client";

import { useState } from "react";
import { useWorkStatus } from "@/hooks/useWorkStatus";
import type { AssignmentAction, WorkStatusAssignment } from "@/types/workStatus";
import CurrentAssignmentCard from "./CurrentAssignmentCard";
import ProjectAssignmentDialog from "./ProjectAssignmentDialog";
import WorkStatusHistory from "./WorkStatusHistory";

interface Props {
  // Omit for the signed-in employee's own Work Status; pass an employee ID for admin/manager views.
  employeeId?: string;
}

interface OpenDialog {
  action:     AssignmentAction;
  assignment: WorkStatusAssignment | null;
}

// Current project(s) plus full assignment history. Admins (data.can_manage) can assign a project and edit, extend or
// end one, from the employee drawer or from the employee's workspace ("view as"); everyone else sees it read-only.
// Renders nothing when the viewer isn't allowed to see this employee's Work Status (403/404) so it never shows a dead card.
export default function WorkStatusPanel({ employeeId }: Props) {
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<OpenDialog | null>(null);
  const { data, loading, error, status, refetch } = useWorkStatus(employeeId, page);

  if (status === 403 || status === 404) return null;

  const canManage = Boolean(data?.can_manage);
  const open = (action: AssignmentAction, assignment: WorkStatusAssignment | null) =>
    setDialog({ action, assignment: action === "assign" ? null : assignment });
  const onAction = canManage ? open : undefined;

  return (
    <div className="card mb-16">
      <div className="card-header" style={{ flexWrap: "wrap", gap: 8 }}>
        <div className="card-title"><i className="ti ti-briefcase" /> Work Status</div>
        {canManage && (
          <button className="btn btn-filled btn-sm" type="button" onClick={() => open("assign", null)}>
            <i className="ti ti-plus" /> Assign project
          </button>
        )}
      </div>
      <div className="card-body">
        {loading && !data ? (
          <div style={{ fontSize: 13, color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
          </div>
        ) : error || !data ? (
          <div className="alert alert-error" style={{ fontSize: 12 }}>{error ?? "Could not load Work Status."}</div>
        ) : (
          <>
            {!data.employee_is_active && (
              <div style={{ fontSize: 11, color: "var(--on-variant)", marginBottom: 12 }}>
                This employee has left; history is kept for reference.
              </div>
            )}

            <h4 style={{ fontSize: 12, margin: "0 0 8px" }}>CURRENT PROJECT{data.current.length === 1 ? "" : "S"}</h4>
            {data.current.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 16 }}>
                Not currently assigned to a project.
                {canManage && " Use Assign project, or extend a finished one from the history below."}
              </div>
            ) : (
              data.current.map(assignment => (
                <CurrentAssignmentCard key={assignment.assignment_id} assignment={assignment} onAction={onAction} />
              ))
            )}

            <h4 style={{ fontSize: 12, margin: "16px 0 8px" }}>PROJECT HISTORY</h4>
            {data.history.count === 0 ? (
              <div style={{ fontSize: 13, color: "var(--on-variant)" }}>No project history yet.</div>
            ) : (
              <WorkStatusHistory history={data.history} onPageChange={setPage} onAction={onAction} />
            )}
          </>
        )}
      </div>

      {dialog && data && (
        <ProjectAssignmentDialog
          employeeId={data.employee_id}
          employeeName={data.employee_name}
          action={dialog.action}
          assignment={dialog.assignment}
          onClose={() => setDialog(null)}
          onSaved={refetch}
        />
      )}
    </div>
  );
}
