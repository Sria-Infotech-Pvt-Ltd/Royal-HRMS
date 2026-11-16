"use client";

// Approvals > HR Requests: every employee's HR Help ticket (profile corrections, payroll queries, document requests, ...) for
// the people who answer them. Staff open a ticket with Respond to set its status, write a response, and resolve it.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { HrHelpRequest } from "@/types/hrHelp";
import HrHelpRow from "@/app/dashboard/ess/_components/HrHelpRow";

interface PagedResponse<T> { results: T[]; count: number }

type StatusFilter = "open" | "in_progress" | "resolved" | "all";

const FILTERS: ReadonlyArray<{ value: StatusFilter; label: string }> = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
  { value: "all", label: "All" },
];

interface HrRequestsTabProps {
  /** Called after a ticket was changed, so a count shown elsewhere (the My Approvals row) can refresh. */
  onChanged?: () => void;
}

export default function HrRequestsTab({ onChanged }: HrRequestsTabProps) {
  const [filter, setFilter] = useState<StatusFilter>("open");
  const query = `${API.hrHelp.list}?page_size=100${filter === "all" ? "" : `&status=${filter}`}`;
  const { data, loading, error, refetch } = useFetch<PagedResponse<HrHelpRequest>>(query);
  const requests = data?.results ?? [];
  function handleUpdated() {
    refetch();
    onChanged?.();
  }
  const filterLabel = FILTERS.find(option => option.value === filter)?.label.toLowerCase() ?? "";

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-headset" /> HR requests</div>
        <div role="group" aria-label="Filter by status" style={{ display: "flex", gap: 6 }}>
          {FILTERS.map(option => (
            <button
              key={option.value}
              type="button"
              aria-pressed={filter === option.value}
              className={`btn btn-sm ${filter === option.value ? "btn-filled" : "btn-ghost"}`}
              onClick={() => setFilter(option.value)}
              suppressHydrationWarning
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}
      {loading ? (
        <div className="empty-state"><i className="ti ti-loader-2 spin" /><h3>Loading requests…</h3></div>
      ) : requests.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-headset" />
          <h3>No {filter === "all" ? "" : `${filterLabel} `}HR requests</h3>
          <p>Requests raised by employees will appear here.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Ref</th><th>From</th><th>Topic</th><th>Priority</th><th>Status</th><th>Submitted</th><th>Action</th></tr>
            </thead>
            <tbody>
              {requests.map(entry => <HrHelpRow key={entry.id} entry={entry} canRespond onUpdated={handleUpdated} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
