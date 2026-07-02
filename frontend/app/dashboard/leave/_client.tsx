"use client";

import { useState } from "react";
import LeaveDashboard from "./_components/LeaveDashboard";
import LeaveApprovals from "./_components/LeaveApprovals";
import ApplyLeaveForm from "./_components/ApplyLeaveForm";
import TeamCalendar   from "./_components/TeamCalendar";
import LeaveAnalytics from "./_components/LeaveAnalytics";
import BranchDropdown from "./_components/BranchDropdown";

type TabId = "dashboard" | "apply" | "approvals" | "calendar" | "analytics";

interface Props { role: string }

export default function LeavePageClient({ role }: Props) {
  const isEmployee = role === "employee";

  const ALL_TABS: { id: TabId; label: string; hideForEmployee?: boolean }[] = [
    { id: "dashboard",  label: "Dashboard"      },
    { id: "apply",      label: "Apply Leave"    },
    { id: "approvals",  label: "Approvals",     hideForEmployee: true },
    { id: "calendar",   label: "Team Calendar"  },
    { id: "analytics",  label: "Analytics"      },
  ];

  const tabs = ALL_TABS.filter(t => !(isEmployee && t.hideForEmployee));

  const [active,           setActive]           = useState<TabId>("dashboard");
  const [selectedBranches, setSelectedBranches] = useState<string[]>([]);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Leave Management</div>
          <div className="page-sub">Apply, approve and track all leave requests</div>
        </div>
        {role === "system_admin" && (
          <BranchDropdown selected={selectedBranches} onChange={setSelectedBranches} />
        )}
      </div>

      <div className="tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={`tab${active === tab.id ? " active" : ""}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div>
        {active === "dashboard" && (
          <LeaveDashboard
            role={role}
            selectedBranches={selectedBranches}
            onApply={() => setActive("apply")}
          />
        )}
        {active === "apply"     && <ApplyLeaveForm onCancel={() => setActive("dashboard")} />}
        {active === "approvals" && <LeaveApprovals />}
        {active === "calendar"  && <TeamCalendar />}
        {active === "analytics" && <LeaveAnalytics role={role} />}
      </div>
    </div>
  );
}
