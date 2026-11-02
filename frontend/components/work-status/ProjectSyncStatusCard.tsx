"use client";

import { useState } from "react";
import { useProjectSyncStatus } from "@/hooks/useWorkStatus";
import { fmtDateTime } from "./workStatusFormat";

const LOG_BADGE: Record<string, string> = {
  success:   "badge badge-success",
  failed:    "badge badge-error",
  unmatched: "badge badge-warn",
};

// Admin view of the Project Budgeting sync: last synced, recent failures, employee IDs we couldn't match, and the log.
export default function ProjectSyncStatusCard() {
  const [page, setPage] = useState(1);
  const { data, loading, error } = useProjectSyncStatus(page);

  if (loading && !data) return <div style={{ fontSize: 13 }}><i className="ti ti-loader-2 spin" /> Loading…</div>;
  if (error || !data) return <div className="alert alert-error">{error ?? "Could not load sync status."}</div>;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-refresh" /> Project Budgeting sync</div>
      </div>
      <div className="card-body">
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", fontSize: 13, marginBottom: 16 }}>
          <div><b>Last synced:</b> {fmtDateTime(data.last_synced_at)}</div>
          <div><b>Failures (24h):</b> {data.failed_last_24h}</div>
          <div><b>Open assignments:</b> {data.open_assignments}</div>
          <div><b>Scheduled pull:</b> {data.is_pull_configured ? "Configured" : "Not configured (push only)"}</div>
        </div>

        {data.unmatched_employee_ids.length > 0 && (
          <div className="alert alert-warn" style={{ fontSize: 12, marginBottom: 16 }}>
            Project Budgeting sent assignments for employee IDs that don&apos;t exist in AIRA HRMS:{" "}
            <b>{data.unmatched_employee_ids.join(", ")}</b>. Fix the ID in Project Budgeting, or add the employee here.
          </div>
        )}

        <table className="table" style={{ width: "100%", fontSize: 12 }}>
          <thead><tr><th>When</th><th>Source</th><th>Employee</th><th>Result</th><th>Saved / changed / removed</th><th>Message</th></tr></thead>
          <tbody>
            {data.logs.results.map(log => (
              <tr key={`${log.at}-${log.employee_id}-${log.source}`}>
                <td>{fmtDateTime(log.at)}</td>
                <td>{log.source}</td>
                <td>{log.employee_id || "All"}</td>
                <td><span className={LOG_BADGE[log.status] ?? "badge badge-neutral"} style={{ fontSize: 10 }}>{log.status}</span></td>
                <td>{log.saved} / {log.changed} / {log.removed}</td>
                <td style={{ color: "var(--on-variant)" }}>{log.message || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.logs.total_pages > 1 && (
          <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, paddingTop: 8 }}>
            <button className="btn btn-outlined" disabled={data.logs.page <= 1} onClick={() => setPage(data.logs.page - 1)}>Previous</button>
            <span style={{ fontSize: 12 }}>Page {data.logs.page} of {data.logs.total_pages}</span>
            <button className="btn btn-outlined" disabled={data.logs.page >= data.logs.total_pages} onClick={() => setPage(data.logs.page + 1)}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
}
