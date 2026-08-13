"use client";

import type { SeparationRequest } from "@/types/separation";
import { fmtDate, statusBadgeClass } from "../_workflow";

interface Props {
  requests: SeparationRequest[];
  onView:   (r: SeparationRequest) => void;
  onEdit:   (r: SeparationRequest) => void;
  onCancel: (r: SeparationRequest) => void;
  onDelete: (r: SeparationRequest) => void;
}

export default function SeparationTable({ requests, onView, onEdit, onCancel, onDelete }: Props) {
  if (requests.length === 0) {
    return (
      <div style={{ padding: "48px 20px", textAlign: "center" }}>
        <i className="ti ti-logout" style={{ fontSize: 32, color: "var(--outline)", display: "block", marginBottom: 10 }} />
        <p style={{ fontSize: 13, color: "var(--on-variant)" }}>No separation requests match your filters.</p>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Request</th>
            <th>Employee</th>
            <th>Employee Code</th>
            <th>Separation Type</th>
            <th>Reason</th>
            <th>Request Date</th>
            <th>Proposed Last Working Day</th>
            <th>Notice Period</th>
            <th>Status</th>
            <th>Reporting Manager</th>
            <th style={{ textAlign: "right" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {requests.map(r => (
            <tr key={r.id} onClick={() => onView(r)} style={{ cursor: "pointer" }}>
              <td style={{ color: "var(--on-variant)" }}>
                {r.request_ref}
                {r.can_approve && <span className="badge badge-error" style={{ marginLeft: 6, fontSize: 10 }}>Action needed</span>}
              </td>
              <td style={{ fontWeight: 600 }}>{r.employee_name}</td>
              <td style={{ color: "var(--on-variant)" }}>{r.employee_code}</td>
              <td>{r.separation_type_display}</td>
              <td>{r.reason_display}</td>
              <td>{fmtDate(r.request_date)}</td>
              <td>{fmtDate(r.proposed_last_working_day)}</td>
              <td>{r.notice_period_days} days</td>
              <td><span className={`badge ${statusBadgeClass(r.status)}`}>{r.status_display}</span></td>
              <td style={{ color: "var(--on-variant)" }}>{r.reporting_manager?.name ?? "Not assigned"}</td>
              <td onClick={e => e.stopPropagation()}>
                <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => onView(r)} title="View" suppressHydrationWarning>
                    <i className="ti ti-eye" />
                  </button>
                  {r.can_edit && (
                    <button className="btn btn-ghost btn-sm" onClick={() => onEdit(r)} title="Edit" suppressHydrationWarning>
                      <i className="ti ti-edit" />
                    </button>
                  )}
                  {r.can_cancel && (
                    <button className="btn btn-ghost btn-sm" onClick={() => onCancel(r)} title="Cancel Request" suppressHydrationWarning>
                      <i className="ti ti-ban" />
                    </button>
                  )}
                  {r.can_delete && (
                    <button className="btn btn-ghost btn-sm" onClick={() => onDelete(r)} title="Reject" style={{ color: "var(--error)" }} suppressHydrationWarning>
                      <i className="ti ti-x" />
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
