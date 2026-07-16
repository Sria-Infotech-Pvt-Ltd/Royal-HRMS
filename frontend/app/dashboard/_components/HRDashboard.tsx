"use client";

import DeptHeadcountChart        from "@/components/dashboard/DeptHeadcountChart";
import HrConsole                 from "@/components/dashboard/hr/HrConsole";
import HrAttendanceSummary       from "@/components/dashboard/hr/HrAttendanceSummary";
import HrActionQueue             from "@/components/dashboard/hr/HrActionQueue";
import HrRecruitmentFunnel       from "@/components/dashboard/hr/HrRecruitmentFunnel";
import HrAttendanceCard          from "@/components/dashboard/hr/HrAttendanceCard";
import HrEmployeeLifecycleTabs   from "@/components/dashboard/hr/HrEmployeeLifecycleTabs";
import HrBirthdaysWidget         from "@/components/dashboard/hr/HrBirthdaysWidget";
import { API }                   from "@/lib/api/endpoints";
import type { SessionPayload }   from "@/lib/session";

interface Props { session: SessionPayload }

const QUICK_ACTIONS = [
  { href: "/dashboard/interview-list",   icon: "ti-users",        bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "Interview List"    },
  { href: "/dashboard/leave",            icon: "ti-beach",        bg: "rgba(27,138,107,0.12)", color: "var(--success)", label: "Leave Approvals"   },
  { href: "/dashboard/payroll",          icon: "ti-report-money", bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "Run Payroll"       },
  { href: "/dashboard/employees",        icon: "ti-id-badge",     bg: "rgba(14,124,134,0.12)", color: "var(--info)",    label: "Employees"         },
  { href: "/dashboard/candidate-review", icon: "ti-user-check",   bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "Review Candidates" },
  { href: "/dashboard/settings",         icon: "ti-settings",     bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "Settings"          },
];

export default function HRDashboard({ session }: Props) {
  const firstName = session.name.split(" ")[0];

  return (
    <>
      {/* Row 1 — Console banner with live KPIs */}
      <HrConsole firstName={firstName} />

      {/* Quick Actions */}
      <div className="card mb-20">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-bolt" /> Quick Actions</div>
        </div>
        <div className="card-body">
          <div className="qa-grid">
            {QUICK_ACTIONS.map(action => (
              <a key={action.href} href={action.href} className="qa-tile">
                <div className="qa-icon" style={{ background: action.bg, color: action.color }}>
                  <i className={`ti ${action.icon}`} />
                </div>
                <span className="qa-label">{action.label}</span>
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* Row 2 — Attendance + Action Queue | Funnel + Attendance Card */}
      <div className="grid-2 mb-16">
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <HrAttendanceSummary />
          <HrActionQueue />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <HrRecruitmentFunnel />
          <HrAttendanceCard />
        </div>
      </div>

      {/* Row 3 — Lifecycle | Dept Headcount */}
      <div className="grid-2 mb-16">
        <HrEmployeeLifecycleTabs />
        <DeptHeadcountChart endpoint={API.dashboard.hrDepartmentHeadcount} />
      </div>

      {/* Row 4 — Birthdays | placeholder */}
      <div className="grid-2">
        <HrBirthdaysWidget />
        <div />
      </div>
    </>
  );
}
