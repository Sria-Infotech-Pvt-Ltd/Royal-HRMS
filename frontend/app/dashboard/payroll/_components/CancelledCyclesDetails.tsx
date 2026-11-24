"use client";

import type { PayrollCycle } from "@/types/payroll";
import { formatDate } from "@/lib/formatDate";
import { cyclePeriodLabel } from "./payrollDashboardShared";
import { useT } from "@/hooks/useI18n";

export default function CancelledCyclesDetails({ cycles }: { cycles: PayrollCycle[] }) {
  const t = useT();
  const cancelled = cycles.filter(c => c.status === "cancelled");
  return (
    <details className="card" style={{ padding: 0 }}>
      <summary style={{ padding: "12px 16px", cursor: "pointer", fontWeight: 600, fontSize: 13, listStyle: "none", display: "flex", alignItems: "center", gap: 8 }}>
        <i className="ti ti-ban" style={{ color: "var(--error)" }} />
        {t("Cancelled Cycles ({count})", { count: cancelled.length })}
      </summary>
      <div className="table-wrap">
        <table>
          <thead><tr><th>{t("Period")}</th><th>{t("Cancelled By")}</th><th>{t("Cancelled At")}</th><th>{t("Reason")}</th></tr></thead>
          <tbody>
            {cancelled.map(c => (
              <tr key={c.id}>
                <td style={{ fontWeight: 600, fontSize: 13 }}>
                  {cyclePeriodLabel(c)}
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
