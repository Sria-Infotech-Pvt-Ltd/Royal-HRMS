"use client";

// Approvals > Timesheets: the weekly timesheets waiting for this person (or, with the filter, every one they can see), with
// employee, week, project / billable / attendance hours and when it was submitted. "Review" opens the read-only sheet.

import { useState } from "react";
import TimesheetStatusBadge from "@/components/timesheet/TimesheetStatusBadge";
import { useTimesheetQueue, type QueueFilter } from "@/hooks/useTimesheetQueue";
import { weekRangeLabel } from "@/lib/timesheet";
import TimesheetDetailDrawer from "./TimesheetDetailDrawer";

const FILTERS: { value: QueueFilter; label: string }[] = [
  { value: "submitted", label: "Waiting for me" },
  { value: "approved", label: "Approved" },
  { value: "returned", label: "Sent back" },
  { value: "all", label: "All" },
];

function submittedOn(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "—";
}

export default function TimesheetApprovalsTab() {
  const [filter, setFilter] = useState<QueueFilter>("submitted");
  const [pageNumber, setPageNumber] = useState(1);
  const [openId, setOpenId] = useState<string | null>(null);
  const { page, loading, error, refetch } = useTimesheetQueue(filter, pageNumber);
  const rows = page?.results ?? [];

  function chooseFilter(next: QueueFilter) {
    setFilter(next);
    setPageNumber(1);
  }

  return (
    <div className="card">
      <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <div className="card-title"><i className="ti ti-clock-check" /> Timesheets</div>
        <div role="group" aria-label="Filter timesheets" style={{ display: "flex", gap: 6 }}>
          {FILTERS.map(option => (
            <button key={option.value} type="button" aria-pressed={filter === option.value} onClick={() => chooseFilter(option.value)}
              className={`btn btn-sm ${filter === option.value ? "btn-filled" : "btn-outline"}`}>
              {option.label}{option.value === "submitted" && page ? ` (${page.pending_count})` : ""}
            </button>
          ))}
        </div>
      </div>
      <div className="table-wrap">
        <table aria-label="Timesheets">
          <thead>
            <tr><th>Employee</th><th>Week</th><th>Project hours</th><th>Billable</th><th>Attendance</th><th>Submitted</th><th>Status</th><th /></tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={8} style={{ textAlign: "center", padding: 24 }}>Loading…</td></tr>}
            {!loading && error && <tr><td colSpan={8} role="alert" style={{ textAlign: "center", padding: 24 }}>{error}</td></tr>}
            {!loading && !error && rows.length === 0 && (
              <tr><td colSpan={8} style={{ textAlign: "center", padding: 24 }}>{filter === "submitted" ? "No timesheets are waiting for you." : "No timesheets to show."}</td></tr>
            )}
            {!loading && rows.map(row => (
              <tr key={row.id}>
                <td><div style={{ fontWeight: 600 }}>{row.employee.name}</div><div style={{ fontSize: 11, color: "var(--on-variant)" }}>{row.employee.employee_id}</div></td>
                <td>{weekRangeLabel(row.week_start, row.week_end)}</td>
                <td>{row.total_hours}</td>
                <td>{row.billable_hours}</td>
                <td>{row.attendance_hours}</td>
                <td>{submittedOn(row.submitted_at)}</td>
                <td><TimesheetStatusBadge status={row.status} isLate={row.is_late} /></td>
                <td><button className="btn btn-outline btn-sm" onClick={() => setOpenId(row.id)}>Review</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {page && page.total_pages > 1 && (
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", alignItems: "center", padding: "10px 16px" }}>
          <button className="btn btn-outline btn-sm" disabled={pageNumber <= 1} onClick={() => setPageNumber(pageNumber - 1)}>Previous</button>
          <span style={{ fontSize: 12 }}>Page {page.page} of {page.total_pages}</span>
          <button className="btn btn-outline btn-sm" disabled={pageNumber >= page.total_pages} onClick={() => setPageNumber(pageNumber + 1)}>Next</button>
        </div>
      )}
      <TimesheetDetailDrawer timesheetId={openId} onClose={() => setOpenId(null)} onChanged={refetch} />
    </div>
  );
}
