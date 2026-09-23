"use client";

import type { PayrollCycle } from "@/types/payroll";
import { formatDate } from "@/lib/formatDate";

export default function CancelledCyclesDetails({ cycles }: { cycles: PayrollCycle[] }) {
  const cancelled = cycles.filter(c => c.status === "cancelled");
  return (
    <details className="card" style={{ padding: 0 }}>
      <summary style={{ padding: "12px 16px", cursor: "pointer", fontWeight: 600, fontSize: 13, listStyle: "none", display: "flex", alignItems: "center", gap: 8 }}>
        <i className="ti ti-ban" style={{ color: "var(--error)" }} />
        Cancelled Cycles ({cancelled.length})
      </summary>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Period</th><th>Cancelled By</th><th>Cancelled At</th><th>Reason</th></tr></thead>
          <tbody>
            {cancelled.map(c => (
              <tr key={c.id}>
                <td style={{ fontWeight: 600, fontSize: 13 }}>
                  {new Date(c.cycle_start).toLocaleString("en-IN", { month: "long", year: "numeric" })}
                </td>
                <td style={{ fontSize: 13 }}>{c.cancelled_by_name ?? "—"}</td>
                <td style={{ fontSize: 13, color: "var(--on-variant)" }}>
                  {c.cancelled_at ? formatDate(c.cancelled_at) : "—"}
                </td>
                <td style={{ fontSize: 13, color: "var(--on-variant)", maxWidth: 300 }}>{c.cancellation_reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
