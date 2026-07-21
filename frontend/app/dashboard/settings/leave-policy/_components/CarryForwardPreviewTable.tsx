"use client";

import type { CarryForwardPreviewResponse } from "@/types/leave";

interface Props {
  preview: CarryForwardPreviewResponse;
}

export default function CarryForwardPreviewTable({ preview }: Props) {
  const { total_rows, pending_count, already_processed_count, preview_rows, from_year, to_year } = preview;

  return (
    <div className="card mb-20">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-eye" /> Preview — {from_year} → {to_year}</div>
        <div style={{ display: "flex", gap: 8 }}>
          <span className="badge badge-neutral">Total Rows: {total_rows}</span>
          <span className="badge badge-success">To Process: {pending_count}</span>
          <span className="badge badge-neutral">Already Done: {already_processed_count}</span>
        </div>
      </div>

      {total_rows === 0 ? (
        <div className="empty-state">
          <i className="ti ti-calendar-off" />
          <h3>Nothing to carry forward</h3>
          <p>No employees have unused leave to carry forward for this period.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee ID</th>
                <th>Employee Name</th>
                <th>Leave Type</th>
                <th style={{ textAlign: "right" }}>Unused Days</th>
                <th style={{ textAlign: "right" }}>Carry Forward</th>
                <th>Expiry Date</th>
                <th style={{ textAlign: "center" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview_rows.map((row, i) => (
                <tr key={`${row.employee_id}-${row.leave_type}-${i}`} style={row.already_processed ? { opacity: 0.55, color: "var(--on-variant)" } : undefined}>
                  <td>{row.employee_id}</td>
                  <td>{row.employee_name}</td>
                  <td>{row.leave_type_display}</td>
                  <td style={{ textAlign: "right" }}>{row.unused_days}</td>
                  <td style={{ textAlign: "right", fontWeight: 700 }}>{row.carry_forward_amount}</td>
                  <td>{row.expiry_date ?? "Never"}</td>
                  <td style={{ textAlign: "center" }}>
                    {row.already_processed
                      ? <span className="badge badge-neutral">Already Done</span>
                      : <span className="badge badge-info">Pending</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
