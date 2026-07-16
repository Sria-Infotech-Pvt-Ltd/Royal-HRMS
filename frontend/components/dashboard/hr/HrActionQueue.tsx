"use client";

import Link from "next/link";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { HRActionQueue } from "@/types/dashboard";

const ROWS: { key: keyof Omit<HRActionQueue, "total_pending">; label: string; icon: string; href: string }[] = [
  { key: "candidate_reviews",      label: "Candidate Reviews",       icon: "ti-user-search",  href: "/dashboard/recruitment"     },
  { key: "leave_approvals",        label: "Leave Approvals",         icon: "ti-calendar-off", href: "/dashboard/leave"           },
  { key: "attendance_corrections", label: "Attendance Corrections",  icon: "ti-clock-edit",   href: "/dashboard/attendance"      },
  { key: "expense_claims",         label: "Expense Claims",          icon: "ti-receipt",      href: "/dashboard/expenses"        },
  { key: "onboarding_reviews",     label: "Onboarding Reviews",      icon: "ti-id-badge",     href: "/dashboard/employees"       },
  { key: "separation_requests",    label: "Separation Requests",     icon: "ti-user-minus",   href: "/dashboard/employees"       },
];

export default function HrActionQueue() {
  const { data, loading } = useFetch<HRActionQueue>(API.dashboard.hrActionQueue);

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-checks" /> Action Queue</div>
        {!loading && data && data.total_pending > 0 && (
          <span className="badge badge-error">{data.total_pending} pending</span>
        )}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : (
        <div style={{ padding: "4px 0 8px" }}>
          {ROWS.map(row => {
            const count = data?.[row.key] ?? 0;
            const isEmpty = count === 0;
            return (
              <Link
                key={row.key}
                href={row.href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "9px 20px",
                  textDecoration: "none",
                  transition: "background 0.15s",
                  opacity: isEmpty ? 0.45 : 1,
                  pointerEvents: isEmpty ? "none" : "auto",
                }}
                className="action-row"
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <i className={`ti ${row.icon}`} style={{ fontSize: 15, color: isEmpty ? "var(--on-variant)" : "var(--primary)", width: 18 }} />
                  <span style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{row.label}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {count > 0 && (
                    <span style={{
                      minWidth: 22, height: 22, borderRadius: 11, background: "var(--error)",
                      color: "#fff", fontSize: 11, fontWeight: 700,
                      display: "inline-flex", alignItems: "center", justifyContent: "center",
                      padding: "0 6px",
                    }}>{count}</span>
                  )}
                  <i className="ti ti-chevron-right" style={{ fontSize: 13, color: "var(--on-variant)" }} />
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
