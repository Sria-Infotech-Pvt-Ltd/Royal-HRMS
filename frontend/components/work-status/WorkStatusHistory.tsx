"use client";

import type { WorkStatusHistoryPage } from "@/types/workStatus";
import { STATUS_BADGE, changeLabel, endLabel, fmtDate, statusLabel } from "./workStatusFormat";

interface Props {
  history:      WorkStatusHistoryPage;
  onPageChange: (page: number) => void;
}

export default function WorkStatusHistory({ history, onPageChange }: Props) {
  return (
    <>
      <div style={{ overflowX: "auto" }}>
        <table className="table" style={{ width: "100%", fontSize: 12 }}>
          <thead>
            <tr>
              <th>Project</th><th>Role</th><th>Allocation</th><th>Start</th><th>End</th><th>Status</th><th>Last change</th>
            </tr>
          </thead>
          <tbody>
            {history.results.map(assignment => (
              <tr key={assignment.assignment_id}>
                <td>
                  <div style={{ fontWeight: 500 }}>{assignment.project_name}</div>
                  <div style={{ color: "var(--on-variant)" }}>
                    {assignment.project_code || `ID ${assignment.project_id}`} · {assignment.milestone_name || "Whole project"}
                  </div>
                </td>
                <td>{assignment.role || "—"}</td>
                <td>{assignment.allocation_percent ? `${assignment.allocation_percent}%` : "—"}</td>
                <td>{fmtDate(assignment.start_date)}</td>
                <td>{endLabel(assignment)}</td>
                <td>
                  <span className={STATUS_BADGE[assignment.assignment_status] ?? "badge badge-neutral"} style={{ fontSize: 10 }}>
                    {statusLabel(assignment)}
                  </span>
                </td>
                <td style={{ color: "var(--on-variant)" }}>{changeLabel(assignment.last_change)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {history.total_pages > 1 && (
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, padding: "8px 0" }}>
          <button className="btn btn-outlined" disabled={history.page <= 1} onClick={() => onPageChange(history.page - 1)}>Previous</button>
          <span style={{ fontSize: 12 }}>Page {history.page} of {history.total_pages}</span>
          <button className="btn btn-outlined" disabled={history.page >= history.total_pages} onClick={() => onPageChange(history.page + 1)}>Next</button>
        </div>
      )}
    </>
  );
}
