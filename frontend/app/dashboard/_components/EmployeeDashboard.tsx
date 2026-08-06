"use client";

import EmpConsole          from "@/components/dashboard/employee/EmpConsole";
import EmpBirthdayAnnouncement from "@/components/dashboard/employee/EmpBirthdayAnnouncement";
import EmpLeaveBalances    from "@/components/dashboard/employee/EmpLeaveBalances";
import EmpUpcomingHolidays from "@/components/dashboard/employee/EmpUpcomingHolidays";
import EmpActionItems      from "@/components/dashboard/employee/EmpActionItems";
import EmpRecentRequests   from "@/components/dashboard/employee/EmpRecentRequests";
import EmpUpdatesCard      from "@/components/dashboard/employee/EmpUpdatesCard";
import type { SessionPayload } from "@/lib/session";

interface Props { session: SessionPayload }

const QUICK_ACTIONS = [
  { href: "/dashboard/leave",         icon: "ti-beach",       bg: "rgba(27,138,107,0.12)", color: "var(--success)", label: "Apply Leave"  },
  { href: "/dashboard/my-payslip",    icon: "ti-receipt",     bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "My Payslips"  },
  { href: "/dashboard/my-attendance", icon: "ti-clock",       bg: "rgba(14,124,134,0.12)", color: "var(--info)",    label: "Attendance"   },
  { href: "/dashboard/expenses",      icon: "ti-wallet",      bg: "rgba(181,101,29,0.12)", color: "var(--warn)",    label: "My Expenses"  },
  { href: "/dashboard/documents",     icon: "ti-folder",      bg: "rgba(30,78,140,0.12)",  color: "var(--primary)", label: "Documents"    },
  { href: "/dashboard/profile",       icon: "ti-user-circle", bg: "rgba(14,124,134,0.12)", color: "var(--info)",    label: "My Profile"   },
];

export default function EmployeeDashboard({ session }: Props) {
  const firstName = session.name.split(" ")[0];

  return (
    <>
      {/* Birthday Announcement — highest priority; renders nothing when nobody
          has a birthday today, so this is a no-op on every non-birthday day */}
      <EmpBirthdayAnnouncement />

      {/* Row 1 + 2 — Console banner (KPIs + attendance status strip) */}
      <EmpConsole firstName={firstName} />

      {/* Row 2.5 — Announcement + today's birthdays, one combined card (renders nothing when both are empty/dismissed) */}
      <EmpUpdatesCard />

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

      {/* Row 3 — Leave Balance | Upcoming Holidays */}
      <div className="grid-2 mb-16">
        <EmpLeaveBalances />
        <EmpUpcomingHolidays />
      </div>

      {/* Row 4 — Pending Requests | Recent Activity */}
      <div className="grid-2 mb-16">
        <EmpActionItems />
        <EmpRecentRequests />
      </div>
    </>
  );
}
