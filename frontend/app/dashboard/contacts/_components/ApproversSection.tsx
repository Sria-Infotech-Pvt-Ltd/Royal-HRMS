"use client";

// L1 / L2 approvers for the selected workflow, read-only, straight from the
// approval routing (per-employee override, else the workflow rule resolved to
// the employee's reporting manager / HR). Everyone gets "My Approvers"; users
// with employees.view also get the employees in their scope.

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import {
  DEFAULT_APPROVER_WORKFLOW, NOT_ASSIGNED, filterApproverRows,
  type ApproverContact, type ApproversResponse,
} from "@/lib/contactMatrix";

function ApproverCell({ approver }: { approver: ApproverContact | null }) {
  if (!approver) return <span style={{ color: "var(--outline)" }}>{NOT_ASSIGNED}</span>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
      <strong>{approver.name}</strong>
      <span style={{ fontSize: 12 }}>
        {approver.email ? <a href={`mailto:${approver.email}`}>{approver.email}</a> : <span style={{ color: "var(--outline)" }}>No email</span>}
      </span>
      <span style={{ fontSize: 12 }}>
        {approver.phone ? <a href={`tel:${approver.phone}`}>{approver.phone}</a> : <span style={{ color: "var(--outline)" }}>No phone</span>}
      </span>
    </div>
  );
}

export default function ApproversSection() {
  const [workflow, setWorkflow] = useState(DEFAULT_APPROVER_WORKFLOW);
  const [query, setQuery]       = useState("");
  const { data, loading, error } = useFetch<ApproversResponse>(API.companyPolicy.contactApprovers(workflow));

  const workflows = data?.workflows ?? [];
  const team = data?.team ? filterApproverRows(data.team, query) : null;

  return (
    <>
      <div className="card mb-16">
        <div className="card-header" style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div className="card-title"><i className="ti ti-user-check" /> My Approvers</div>
          <select
            className="field-input"
            style={{ width: 220, marginLeft: "auto" }}
            aria-label="Approval workflow"
            value={workflow}
            onChange={e => setWorkflow(e.target.value)}
          >
            {(workflows.length ? workflows : [{ value: DEFAULT_APPROVER_WORKFLOW, label: "Leave Request" }]).map(w => (
              <option key={w.value} value={w.value}>{w.label}</option>
            ))}
          </select>
        </div>
        <div className="card-body">
          {error && <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error}</div>}
          {loading && !data && <div>Loading…</div>}
          {data && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
              <div><div className="field-label">L1 Approver</div><ApproverCell approver={data.me.l1} /></div>
              <div><div className="field-label">L2 Approver</div><ApproverCell approver={data.me.l2} /></div>
            </div>
          )}
          {workflow === "expense" && (
            <div style={{ marginTop: 12, fontSize: 12, color: "var(--on-variant)" }}>
              <i className="ti ti-info-circle" /> Expense claims are approved in one step by the reporting manager or
              assigned HR; the approvers above are the configured Expense approval rule.
            </div>
          )}
        </div>
      </div>

      {team !== null && data && (
        <div className="card mb-16">
          <div className="card-header" style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <div className="card-title"><i className="ti ti-users" /> Employee Approvers</div>
            <input
              className="field-input"
              style={{ width: 240, marginLeft: "auto" }}
              aria-label="Search employees"
              placeholder="Search name, ID, department…"
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Employee</th><th>L1 Approver</th><th>L2 Approver</th></tr>
              </thead>
              <tbody>
                {team.length === 0 && (
                  <tr><td colSpan={3} style={{ color: "var(--on-variant)" }}>
                    {query ? "No matching employees." : "No employees in your scope."}
                  </td></tr>
                )}
                {team.map(r => (
                  <tr key={r.employee_id}>
                    <td>
                      <strong>{r.name}</strong>
                      <div style={{ fontSize: 11, color: "var(--outline)" }}>
                        {[r.employee_id, r.department, r.branch].filter(Boolean).join(" · ")}
                      </div>
                    </td>
                    <td><ApproverCell approver={r.l1} /></td>
                    <td><ApproverCell approver={r.l2} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
