"use client";

import { useState } from "react";
import { useWorkStatus } from "@/hooks/useWorkStatus";
import WorkStatusHistory from "./WorkStatusHistory";
import { STATUS_BADGE, endLabel, fmtDate, fmtDateTime, statusLabel } from "./workStatusFormat";

interface Props {
  // Omit for the signed-in employee's own Work Status; pass an employee ID for HR/admin/manager views.
  employeeId?: string;
}

// Current project(s) plus full assignment history. Assignments are managed in Project Budgeting, so this is read-only.
// Renders nothing when the viewer isn't allowed to see this employee's Work Status (403/404) so it never shows a dead card.
export default function WorkStatusPanel({ employeeId }: Props) {
  const [page, setPage] = useState(1);
  const { data, loading, error, status } = useWorkStatus(employeeId, page);

  if (status === 403 || status === 404) return null;

  return (
    <div className="card mb-16">
      <div className="card-header" style={{ flexWrap: "wrap", gap: 8 }}>
        <div className="card-title"><i className="ti ti-briefcase" /> Work Status</div>
        <span className="badge badge-neutral" title="Edit assignments in Project Budgeting; they sync here automatically.">
          <i className="ti ti-lock" /> Managed in Project Budgeting
        </span>
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
            <div style={{ fontSize: 11, color: "var(--on-variant)", marginBottom: 12 }}>
              Last synced: {fmtDateTime(data.last_synced_at)}
              {!data.employee_is_active && " · This employee has left; history is kept for reference."}
            </div>

            {data.conflicts.map(conflict => (
              <div key={conflict.message} className="alert alert-warn" style={{ fontSize: 12, marginBottom: 8 }}>{conflict.message}</div>
            ))}

            <h4 style={{ fontSize: 12, margin: "0 0 8px" }}>CURRENT ASSIGNMENT{data.current.length === 1 ? "" : "S"}</h4>
            {data.current.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 16 }}>Not currently assigned to a project.</div>
            ) : (
              data.current.map(assignment => (
                <div key={assignment.assignment_id} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "10px 14px", marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{assignment.project_name}</div>
                    <span className={STATUS_BADGE[assignment.assignment_status] ?? "badge badge-neutral"} style={{ fontSize: 10 }}>
                      {statusLabel(assignment)}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                    {assignment.project_code || `Project ID ${assignment.project_id}`}
                    {" · "}{assignment.milestone_name || "Whole project"}
                    {assignment.role && ` · ${assignment.role}`}
                    {assignment.allocation_percent && ` · ${assignment.allocation_percent}% allocated`}
                  </div>
                  <div style={{ fontSize: 12, marginTop: 4 }}>
                    {fmtDate(assignment.start_date)} – {endLabel(assignment)}
                  </div>
                </div>
              ))
            )}

            <h4 style={{ fontSize: 12, margin: "16px 0 8px" }}>ASSIGNMENT HISTORY</h4>
            {data.history.count === 0 ? (
              <div style={{ fontSize: 13, color: "var(--on-variant)" }}>No project history yet.</div>
            ) : (
              <WorkStatusHistory history={data.history} onPageChange={setPage} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
