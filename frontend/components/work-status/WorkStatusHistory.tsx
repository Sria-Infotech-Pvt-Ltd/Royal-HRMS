"use client";

import type { AssignmentAction, WorkStatusAssignment, WorkStatusHistoryPage } from "@/types/workStatus";
import { changeLabel, endLabel, fmtDate, statusBadge, statusLabel, workPlaceLabel } from "./workStatusFormat";

interface Props {
  history:      WorkStatusHistoryPage;
  onPageChange: (page: number) => void;
  /** Present only for admins: lets them extend a finished project (which re-opens it). */
  onAction?:    (action: AssignmentAction, assignment: WorkStatusAssignment) => void;
}

export default function WorkStatusHistory({ history, onPageChange, onAction }: Props) {
  return (
    <>
      <div style={{ overflowX: "auto" }}>
        <table className="table" style={{ width: "100%", fontSize: 12 }}>
          <thead>
            <tr>
              <th>Project</th><th>Role</th><th>Work mode</th><th>Start</th><th>End</th><th>Status</th><th>Last change</th>
              {onAction && <th />}
            </tr>
          </thead>
          <tbody>
            {history.results.map(assignment => (
              <tr key={assignment.assignment_id}>
                <td>
                  <div style={{ fontWeight: 500 }}>{assignment.project_name}</div>
                  {assignment.notes && <div style={{ color: "var(--on-variant)" }}>{assignment.notes}</div>}
                </td>
                <td>{assignment.role || "—"}</td>
                <td>{workPlaceLabel(assignment)}</td>
                <td>{fmtDate(assignment.start_date)}</td>
                <td>{endLabel(assignment)}</td>
                <td>
                  <span className={statusBadge(assignment)} style={{ fontSize: 10 }}>{statusLabel(assignment)}</span>
                </td>
                <td style={{ color: "var(--on-variant)" }}>
                  {changeLabel(assignment.last_change)}
                  {assignment.last_change?.reason && <div>“{assignment.last_change.reason}”</div>}
                </td>
                {onAction && (
                  <td>
                    {assignment.assignment_status === "completed" && (
                      <button className="btn btn-outline btn-sm" type="button" onClick={() => onAction("extend", assignment)}>
                        <i className="ti ti-calendar-plus" /> Extend
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {history.total_pages > 1 && (
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, padding: "8px 0" }}>
          <button className="btn btn-outline btn-sm" disabled={history.page <= 1} onClick={() => onPageChange(history.page - 1)}><i className="ti ti-chevron-left" /> Previous</button>
          <span style={{ fontSize: 12 }}>Page {history.page} of {history.total_pages}</span>
          <button className="btn btn-outline btn-sm" disabled={history.page >= history.total_pages} onClick={() => onPageChange(history.page + 1)}>Next <i className="ti ti-chevron-right" /></button>
        </div>
      )}
    </>
  );
}
