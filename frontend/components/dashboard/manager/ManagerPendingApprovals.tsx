"use client";

import Link from "next/link";
import { useManagerPendingApprovals } from "@/hooks/useManagerDashboard";
import type { PendingApprovalItem } from "@/types/managerDashboard";

const TYPE_META: Record<PendingApprovalItem["type"], { icon: string; color: string }> = {
  leave:   { icon: "ti-beach",  color: "var(--success)" },
  expense: { icon: "ti-wallet", color: "var(--warn)"    },
};

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function describe(item: PendingApprovalItem): { subtitle: string; date: string } {
  const d = item.details;
  if (item.type === "leave") {
    const leaveType = ((d.leave_type as string) ?? "").replace(/_/g, " ");
    const start     = d.start_date as string | undefined;
    const end       = d.end_date   as string | undefined;
    const days      = d.total_days as number | undefined;
    return {
      subtitle: `${leaveType} Leave${days ? ` · ${days}d` : ""}`,
      date: start && end ? `${fmtDate(start)} – ${fmtDate(end)}` : "",
    };
  }
  const amount = d.amount as number | undefined;
  return {
    subtitle: `Expense Claim${amount ? ` · ₹${amount.toLocaleString("en-IN")}` : ""}`,
    date: d.expense_date ? fmtDate(d.expense_date as string) : "",
  };
}

export default function ManagerPendingApprovals() {
  const { data, loading } = useManagerPendingApprovals();
  const items = data?.items ?? [];

  return (
    <div className="card mb-16">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-checks" /> Pending Approvals</div>
        {!loading && (data?.total_pending ?? 0) > 0 && (
          <span className="badge badge-warn">{data?.total_pending} items</span>
        )}
      </div>
      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : items.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          No pending approvals right now.
        </div>
      ) : (
        <div style={{ padding: 0 }}>
          {items.map(item => {
            const meta = TYPE_META[item.type];
            const { subtitle, date } = describe(item);
            return (
              <Link
                key={`${item.type}-${item.id}`}
                href="/dashboard/approvals"
                style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 20px", borderBottom: "1px solid var(--bg-high)", textDecoration: "none" }}
              >
                <div className="qa-icon" style={{ background: "var(--bg-low)", color: meta.color, width: 36, height: 36, fontSize: 16, flexShrink: 0 }}>
                  <i className={`ti ${meta.icon}`} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{item.employee_name}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{subtitle}{date ? ` · ${date}` : ""}</div>
                </div>
                <i className="ti ti-chevron-right" style={{ fontSize: 13, color: "var(--on-variant)" }} />
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
