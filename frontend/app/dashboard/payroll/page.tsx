"use client";

import { useState } from "react";
import PayrollDashboard from "./_components/PayrollDashboard";
import RunPayrollWizard from "./_components/RunPayrollWizard";
import PayrollReports   from "./_components/PayrollReports";
import PayrollAnalytics from "./_components/PayrollAnalytics";

type TabId = "dashboard" | "reports" | "analytics";

const TABS: { id: TabId; label: string }[] = [
  { id: "dashboard",  label: "Dashboard"  },
  { id: "reports",    label: "Reports"    },
  { id: "analytics",  label: "Analytics"  },
];

export default function PayrollPage() {
  const [active,     setActive]     = useState<TabId>("dashboard");
  const [runWizard,  setRunWizard]  = useState(false);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Payroll Management</div>
          <div className="page-sub">Process, approve and disburse salaries — June 2026</div>
        </div>
        {!runWizard && (
          <div className="page-actions">
            <button className="btn btn-ghost btn-sm">
              <i className="ti ti-history" /> View History
            </button>
            <button className="btn btn-filled btn-sm" onClick={() => setRunWizard(true)}>
              <i className="ti ti-player-play" /> Run Payroll
            </button>
          </div>
        )}
      </div>

      {runWizard ? (
        <RunPayrollWizard onCancel={() => setRunWizard(false)} />
      ) : (
        <>
          <div className="tabs">
            {TABS.map(tab => (
              <button
                key={tab.id}
                className={`tab${active === tab.id ? " active" : ""}`}
                onClick={() => setActive(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {active === "dashboard"  && <PayrollDashboard onRunPayroll={() => setRunWizard(true)} />}
          {active === "reports"    && <PayrollReports />}
          {active === "analytics"  && <PayrollAnalytics />}
        </>
      )}
    </div>
  );
}
