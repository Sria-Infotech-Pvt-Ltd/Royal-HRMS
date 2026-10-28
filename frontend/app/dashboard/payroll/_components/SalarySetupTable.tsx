"use client";

import type { SalarySetupRow } from "@/types/salarySetup";

const formatRupees = (amount: number | string) => `₹${Number(amount).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

interface Props {
  rows: SalarySetupRow[];
  onEdit: (row: SalarySetupRow) => void;
}

export default function SalarySetupTable({ rows, onEdit }: Props) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Employee</th>
            <th>Org Unit</th>
            <th>Company Code</th>
            <th style={{ textAlign: "right" }}>Annual CTC</th>
            <th style={{ textAlign: "right" }}>Monthly CTC</th>
            <th>Effective From</th>
            <th>Structure</th>
            <th>Payroll</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.uuid} style={row.state === "missing" ? { background: "var(--warn-c)" } : undefined}>
              <td>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{row.full_name}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{row.employee_id}</div>
              </td>
              <td style={{ fontSize: 13 }}>{row.department || "—"}</td>
              <td style={{ fontSize: 13 }}>{row.branch || "—"}</td>
              <td style={{ textAlign: "right", fontWeight: 600 }}>
                {row.salary ? formatRupees(row.salary.annual_ctc) : <span style={{ color: "var(--warn)", fontSize: 12 }}>Not set</span>}
              </td>
              <td style={{ textAlign: "right", fontSize: 13, color: "var(--on-variant)" }}>{row.salary ? formatRupees(row.salary.monthly_ctc) : "—"}</td>
              <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{row.salary?.effective_from ?? "—"}</td>
              <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{row.salary?.structure_name ?? (row.salary ? "Default" : "—")}</td>
              <td style={{ fontSize: 12 }}>
                {row.payroll_ready ? (
                  <span style={{ color: "var(--success)", fontWeight: 600 }}><i className="ti ti-circle-check" /> Ready</span>
                ) : (
                  <span style={{ color: "var(--warn)" }} title={row.blockers.join("; ")}>
                    <i className="ti ti-alert-triangle" /> {row.blockers[0] ?? "Not ready"}{row.blockers.length > 1 ? ` +${row.blockers.length - 1}` : ""}
                  </span>
                )}
              </td>
              <td>
                <button className="btn btn-ghost btn-sm" type="button" onClick={() => onEdit(row)}>
                  <i className={`ti ${row.salary ? "ti-edit" : "ti-plus"}`} />{row.salary ? " Edit" : " Assign"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
