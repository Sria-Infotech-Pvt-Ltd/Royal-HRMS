"use client";

import type { PayrollCycle } from "@/types/payroll";
import { STATUS_BADGE, STATUS_LABEL, UNCANCELLABLE, PENDING_CYCLES_SECTION_ID } from "./payrollDashboardShared";

interface PendingCyclesCardProps {
  pending: PayrollCycle[];
  canResume: boolean;
  onResumeCycle: (id: string, status: string, cycleStart?: string) => void;
  onCancelCycle: (cycle: PayrollCycle) => void;
}

export default function PendingCyclesCard({ pending, canResume, onResumeCycle, onCancelCycle }: PendingCyclesCardProps) {
  return (
    <div className="card" id={PENDING_CYCLES_SECTION_ID}>
      <div className="card-header">
        <div className="card-title">
          <i className="ti ti-alert-circle" style={{ color: "var(--warn)" }} />
          {" "}Action Required — {pending.length} Pending Cycle{pending.length !== 1 ? "s" : ""}
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Period</th><th>Pay Date</th><th>Status</th>
              <th>L1 Approver</th><th>Payslips</th><th />
            </tr>
          </thead>
          <tbody>
            {pending.map(c => (
              <tr key={c.id} style={{ cursor: canResume ? "pointer" : "default" }} onClick={canResume ? () => onResumeCycle(c.id, c.status, c.cycle_start) : undefined}>
                <td style={{ fontWeight: 600 }}>
                  {new Date(c.cycle_start).toLocaleString("en-IN", { month: "long", year: "numeric" })}
                </td>
                <td>{c.pay_date}</td>
                <td><span className={STATUS_BADGE[c.status] ?? "badge badge-neutral"}>{STATUS_LABEL[c.status] ?? c.status}</span></td>
                <td style={{ fontSize: 13, color: "var(--on-variant)" }}>{c.l1_approver_name ?? "—"}</td>
                <td>{c.payslip_count}</td>
                <td onClick={e => e.stopPropagation()}>
                  {!UNCANCELLABLE.includes(c.status) && (
                    <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)", fontSize: 12 }} onClick={() => onCancelCycle(c)} title="Cancel this cycle">
                      <i className="ti ti-ban" /> Cancel
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
