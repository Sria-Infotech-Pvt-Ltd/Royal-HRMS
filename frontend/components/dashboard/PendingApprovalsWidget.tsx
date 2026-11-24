"use client";

import { useT } from "@/hooks/useI18n";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { PROFILE_CORRECTION_TOPIC } from "@/app/dashboard/ess/_components/ProfileCorrectionModal";
import type { PendingApprovals } from "@/types/dashboard";

interface ApprovalRow {
  key:   string;
  icon:  string;
  bg:    string;
  color: string;
  label: string;
  href:  string;
}

// Profile corrections are HR Help tickets, not approvals, but they wait for the same people, so they get a row here.
const HR_HELP_KEY = "profile_corrections";
const HR_HELP_ROW: ApprovalRow = {
  key: HR_HELP_KEY, icon: "ti-help-circle", bg: "rgba(0,106,159,0.12)", color: "var(--info)", label: "Profile Corrections", href: "/dashboard/approvals?section=hr_requests",
};

const ROWS: ApprovalRow[] = [
  { key: "leave_requests",      icon: "ti-beach",      bg: "rgba(23,144,90,0.12)", color: "var(--success)", label: "Leave Requests",      href: "/dashboard/approvals"   },
  { key: "expense_claims",      icon: "ti-wallet",     bg: "rgba(162,98,12,0.12)", color: "var(--warn)",    label: "Expense Claims",      href: "/dashboard/expenses"    },
  { key: "onboarding_reviews",  icon: "ti-user-check", bg: "color-mix(in srgb, var(--brand) 12%, transparent)",  color: "var(--primary)", label: "Onboarding Reviews",  href: "/dashboard/employees"   },
  { key: "separation_requests", icon: "ti-logout",     bg: "rgba(194,58,47,0.12)",  color: "var(--error)",   label: "Separation Requests", href: "/dashboard/separation"  },
];

export default function PendingApprovalsWidget() {
  const t = useT();
  const { data, loading } = useFetch<PendingApprovals>(API.dashboard.pendingApprovals);
  // Anyone who can see this widget sees every ticket, so the open count is organisation-wide.
  const { data: openTickets } = useFetch<{ count: number }>(`${API.hrHelp.list}?status=open&page_size=1&topic=${PROFILE_CORRECTION_TOPIC}`);

  const openTicketCount = openTickets?.count ?? 0;
  const total = (data?.total_pending ?? 0) + openTicketCount;

  function countFor(row: ApprovalRow): number {
    if (row.key === HR_HELP_KEY) return openTicketCount;
    return data?.[row.key as keyof Omit<PendingApprovals, "total_pending">] ?? 0;
  }

  return (
    <div className="card mb-16">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-checks" /> {t("Pending Approvals")}</div>
        {!loading && (
          <span className="badge badge-warn">{t("{total} pending", { total })}</span>
        )}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> {t("Loading…")}
        </div>
      ) : (
        <div style={{ padding: 0 }}>
          {[...ROWS, HR_HELP_ROW].map(row => {
            const count = countFor(row);
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
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{t(row.label)}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 1 }}>{t("Awaiting action")}</div>
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
          {t("View all pending approvals")} <i className="ti ti-arrow-right" style={{ fontSize: 11 }} />
        </a>
      </div>
    </div>
  );
}
