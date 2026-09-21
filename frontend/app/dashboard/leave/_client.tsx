"use client";

import { useState } from "react";
import LeaveDashboard from "./_components/LeaveDashboard";
import ApplyLeaveForm from "./_components/ApplyLeaveForm";
import TeamCalendar   from "./_components/TeamCalendar";
import LeaveAnalytics from "./_components/LeaveAnalytics";

type TabId = "dashboard" | "apply" | "calendar" | "analytics";

interface Props { initialTab?: TabId; onBack?: () => void }

// Approving leave/expense/attendance-correction requests — for both managers
// and HR — lives entirely in the Approvals module (/dashboard/approvals) now.
// This page is scoped to applying for and tracking one's own leave only.
export default function LeavePageClient({ initialTab = "dashboard", onBack }: Props) {
  const tabs: { id: TabId; label: string }[] = [
    { id: "dashboard", label: "Dashboard"    },
    { id: "apply",     label: "Apply Leave"  },
    { id: "calendar",  label: "Team Calendar" },
    { id: "analytics", label: "Analytics"    },
  ];

  const [active, setActive] = useState<TabId>(initialTab);

  return (
    <div>
      <div className="page-header">
        <div>
          {onBack && (
            <button
              onClick={onBack}
              style={{ display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", color: "var(--primary)", fontSize: 12.5, fontWeight: 700, cursor: "pointer", padding: 0, marginBottom: 8 }}
            >
              <i className="ti ti-arrow-left" /> Back to overview
            </button>
          )}
          <div className="page-title">Leave Management</div>
          <div className="page-sub">Apply for leave and track your own requests</div>
        </div>
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
        {active === "dashboard" && <LeaveDashboard onApply={() => setActive("apply")} onViewCalendar={() => setActive("calendar")} />}
        {active === "apply"     && <ApplyLeaveForm onCancel={() => setActive("dashboard")} />}
        {active === "calendar"  && <TeamCalendar />}
        {active === "analytics" && <LeaveAnalytics />}
      </div>
    </div>
  );
}
