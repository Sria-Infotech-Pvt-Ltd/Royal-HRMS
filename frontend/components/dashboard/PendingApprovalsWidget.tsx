"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PendingApprovals } from "@/types/dashboard";

interface ApprovalRow {
  key:   keyof Omit<PendingApprovals, "total_pending">;
  icon:  string;
  bg:    string;
  color: string;
  label: string;
  href:  string;
}

const ROWS: ApprovalRow[] = [
  { key: "leave_requests",      icon: "ti-beach",      bg: "rgba(27,138,107,0.12)", color: "var(--success)", label: "Leave Requests",      href: "/dashboard/approvals"   },
  { key: "expense_claims",      icon: "ti-wallet",     bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "Expense Claims",      href: "/dashboard/expenses"    },
  { key: "onboarding_reviews",  icon: "ti-user-check", bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "Onboarding Reviews",  href: "/dashboard/employees"   },
  { key: "separation_requests", icon: "ti-logout",     bg: "rgba(192,57,43,0.12)",  color: "var(--error)",   label: "Separation Requests", href: "/dashboard/separation"  },
];

export default function PendingApprovalsWidget() {
  const { data, loading } = useFetch<PendingApprovals>(API.dashboard.pendingApprovals);

  const total = data?.total_pending ?? 0;

  return (
    <div className="card mb-16">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-checks" /> Pending Approvals</div>
        {!loading && (
          <span className="badge badge-warn">{total} pending</span>
        )}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : (
        <div style={{ padding: 0 }}>
          {ROWS.map(row => {
            const count = data?.[row.key] ?? 0;
            return (
              <a
                key={row.key}
                href={row.href}
                style={{ display: "flex", alignItems: "center", gap: 14, padding: "13px 20px", borderBottom: "1px solid var(--bg-high)", textDecoration: "none" }}
              >
                <div className="qa-icon" style={{ background: row.bg, color: row.color, width: 36, height: 36, fontSize: 16, flexShrink: 0 }}>
                  <i className={`ti ${row.icon}`} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{row.label}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 1 }}>Awaiting action</div>
                </div>
                <span style={{ fontSize: 18, fontWeight: 700, color: row.color, minWidth: 24, textAlign: "right" }}>{count}</span>
                <i className="ti ti-chevron-right" style={{ fontSize: 13, color: "var(--outline)", marginLeft: 2 }} />
              </a>
            );
          })}
        </div>
      )}

      <div style={{ padding: "10px 20px", borderTop: "1px solid var(--bg-high)", background: "var(--bg-low)" }}>
        <a href="/dashboard/approvals" style={{ fontSize: 12, color: "var(--primary)", fontWeight: 500, textDecoration: "none" }}>
          View all pending approvals <i className="ti ti-arrow-right" style={{ fontSize: 11 }} />
        </a>
      </div>
    </div>
  );
}
