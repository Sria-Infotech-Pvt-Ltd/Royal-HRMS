"use client";

import { useState } from "react";
import { EMP_DATA, netSalary, fmt } from "./payrollData";

interface Props { onNext: () => void; onBack: () => void; }

type TransferStatus = "pending" | "processing" | "paid";

const STATUS_BADGE: Record<TransferStatus, string> = {
  pending:    "badge badge-warn",
  processing: "badge badge-info",
  paid:       "badge badge-success",
};

export default function BankTransferStep({ onNext, onBack }: Props) {
  const [statuses, setStatuses] = useState<Record<string, TransferStatus>>(
    Object.fromEntries(EMP_DATA.map(e => [e.id, "pending"]))
  );
  const [markAll, setMarkAll] = useState(false);
  const [fileGenerated, setFileGenerated] = useState(false);

  function markPaid(id: string) {
    setStatuses(p => ({ ...p, [id]: "paid" }));
  }

  function markAllPaid() {
    setStatuses(Object.fromEntries(EMP_DATA.map(e => [e.id, "paid"])));
    setMarkAll(true);
  }

  function generateFile() {
    setFileGenerated(true);
    setStatuses(Object.fromEntries(EMP_DATA.map(e => [e.id, "processing"])));
  }

  const totalNet  = EMP_DATA.reduce((s, e) => s + netSalary(e), 0);
  const paidCount = Object.values(statuses).filter(s => s === "paid").length;
  const allPaid   = paidCount === EMP_DATA.length;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-credit-card" /> Bank Transfer</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="badge badge-primary">{fmt(totalNet)} total</span>
          <span className="badge badge-info">Step 11 of 11</span>
        </div>
      </div>

      {allPaid && (
        <div className="alert alert-success" style={{ margin: "0 0 0 0", borderRadius: 0 }}>
          <i className="ti ti-circle-check" />
          <span>All salaries disbursed successfully. June 2026 payroll run is complete.</span>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Employee</th>
              <th>Bank Name</th>
              <th>Account Number</th>
              <th>IFSC Code</th>
              <th style={{ textAlign: "right", color: "var(--success)" }}>Net Salary</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {EMP_DATA.map(e => {
              const net    = netSalary(e);
              const status = statuses[e.id];
              return (
                <tr key={e.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}>{e.avatar}</div>
                      <div>
                        <div style={{ fontWeight: 600 }}>{e.name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{e.dept}</div>
                      </div>
                    </div>
                  </td>
                  <td>{e.bank}</td>
                  <td style={{ fontFamily: "monospace", letterSpacing: "0.05em" }}>{e.account}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>{e.ifsc}</td>
                  <td style={{ textAlign: "right", fontWeight: 700, color: "var(--success)" }}>{fmt(net)}</td>
                  <td><span className={STATUS_BADGE[status]}>{status.charAt(0).toUpperCase() + status.slice(1)}</span></td>
                  <td>
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => markPaid(e.id)}
                      disabled={status === "paid"}
                      style={{ opacity: status === "paid" ? 0.4 : 1 }}
                    >
                      <i className="ti ti-check" /> Mark Paid
                    </button>
                  </td>
                </tr>
              );
            })}
            <tr style={{ background: "var(--bg-low)" }}>
              <td style={{ fontWeight: 700 }} colSpan={4}>Total Net Payable</td>
              <td style={{ textAlign: "right", fontWeight: 800, color: "var(--success)", fontSize: 15 }}>{fmt(totalNet)}</td>
              <td colSpan={2} />
            </tr>
          </tbody>
        </table>
      </div>

      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-outline btn-sm" onClick={generateFile} disabled={fileGenerated}>
            <i className="ti ti-file-export" /> Generate Bank File
          </button>
          <button className="btn btn-ghost btn-sm">
            <i className="ti ti-table-export" /> Export Excel
          </button>
          <button className="btn btn-success btn-sm" onClick={markAllPaid} disabled={markAll}>
            <i className="ti ti-checks" /> Mark All Paid
          </button>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
          <button className="btn btn-filled" onClick={onNext}>
            <i className="ti ti-circle-check" /> Finish Payroll
          </button>
        </div>
      </div>
    </div>
  );
}
