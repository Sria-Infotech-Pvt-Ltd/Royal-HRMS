"use client";

import KpiConsole            from "@/components/dashboard/KpiConsole";
import AnnouncementCard      from "@/components/dashboard/AnnouncementCard";
import PendingApprovalsWidget from "@/components/dashboard/PendingApprovalsWidget";
import DeptHeadcountChart    from "@/components/dashboard/DeptHeadcountChart";
import EmployeeLifecycleTabs from "@/components/dashboard/EmployeeLifecycleTabs";
import BirthdayWidget        from "@/components/dashboard/BirthdayWidget";
import AuditLogsWidget       from "@/components/dashboard/AuditLogsWidget";
import type { SessionPayload } from "@/lib/session";

interface Props { session: SessionPayload }

interface QuickAction {
  href:  string;
  icon:  string;
  bg:    string;
  color: string;
  label: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  { href: "/dashboard/employees",            icon: "ti-id-badge",            bg: "rgba(124,58,237,0.12)",  color: "var(--primary)", label: "Employees"     },
  { href: "/dashboard/settings/permissions", icon: "ti-shield-check",        bg: "rgba(23,144,90,0.12)", color: "var(--success)", label: "Roles & Perms" },
  { href: "/dashboard/attendance",           icon: "ti-clock",               bg: "rgba(37,99,235,0.12)", color: "var(--info)",    label: "Attendance"    },
  { href: "/dashboard/payroll",              icon: "ti-report-money",        bg: "rgba(162,98,12,0.12)", color: "var(--warn)",    label: "Payroll"       },
  { href: "/dashboard/branches",             icon: "ti-building-skyscraper", bg: "rgba(124,58,237,0.12)",  color: "var(--primary)", label: "Company Codes" },
  { href: "/dashboard/settings",             icon: "ti-settings",            bg: "rgba(162,98,12,0.12)", color: "var(--warn)",    label: "Settings"      },
];

export default function AdminDashboard({ session }: Props) {
  const firstName = session.name.split(" ")[0];

  return (
    <>
      {/* KPI Console — welcome + health pills + live stats */}
      <KpiConsole firstName={firstName} />

      {/* Announcement */}
      <AnnouncementCard />

      {/* Quick Actions */}
      <div className="card mb-20">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-bolt" /> Quick Actions</div>
        </div>
        <div className="card-body">
          <div className="qa-grid">
            {QUICK_ACTIONS.map(a => (
              <a key={a.href} href={a.href} className="qa-tile">
                <div className="qa-icon" style={{ background: a.bg, color: a.color }}>
                  <i className={`ti ${a.icon}`} />
                </div>
                <span className="qa-label">{a.label}</span>
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* Row 3 — Pending Approvals + Headcount | Announcement + Lifecycle */}
      <div className="grid-2 mb-20">
        <div>
          <PendingApprovalsWidget />
          <DeptHeadcountChart />
        </div>
        <div>
          <EmployeeLifecycleTabs />
        </div>
      </div>

      {/* Row 4 — Birthdays | Audit Logs */}
      <div className="grid-2">
        <div>
          <BirthdayWidget />
        </div>
        <div>
          <AuditLogsWidget />
        </div>
      </div>
    </>
  );
}
