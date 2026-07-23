"use client";

import type { SessionPayload } from "@/lib/session";
import BirthdayWidget from "@/components/dashboard/BirthdayWidget";
import ManagerConsole from "@/components/dashboard/manager/ManagerConsole";
import ManagerPendingApprovals from "@/components/dashboard/manager/ManagerPendingApprovals";
import ManagerTeamAttendance from "@/components/dashboard/manager/ManagerTeamAttendance";
import ManagerUpcomingLeave from "@/components/dashboard/manager/ManagerUpcomingLeave";
import ManagerRecentActivity from "@/components/dashboard/manager/ManagerRecentActivity";

interface Props { session: SessionPayload }

const QUICK_ACTIONS = [
  { href: "/dashboard/approvals",     icon: "ti-checks",      bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "Review Approvals" },
  { href: "/dashboard/leave",         icon: "ti-beach",       bg: "rgba(27,138,107,0.12)", color: "var(--success)", label: "Apply Leave"      },
  { href: "/dashboard/my-payslip",    icon: "ti-receipt",     bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "My Payslip"       },
  { href: "/dashboard/employees",     icon: "ti-users",       bg: "rgba(14,124,134,0.12)", color: "var(--info)",    label: "Team Members"     },
  { href: "/dashboard/interview-list",icon: "ti-user-search", bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "Interviews"       },
  { href: "/dashboard/my-requests",   icon: "ti-inbox",       bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "My Requests"      },
];

export default function ManagerDashboard({ session }: Props) {
  const firstName = session.name.split(" ")[0];

  return (
    <>
      <ManagerConsole firstName={firstName} />

      {/* Quick actions */}
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

      <div className="grid-2">
        {/* Left */}
        <div>
          <ManagerPendingApprovals />
          <ManagerRecentActivity />
        </div>

        {/* Right */}
        <div>
          <BirthdayWidget />
          <ManagerTeamAttendance />
          <ManagerUpcomingLeave />
        </div>
      </div>
    </>
  );
}
