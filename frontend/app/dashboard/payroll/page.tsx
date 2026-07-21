"use client";

import { useState } from "react";
import { usePermission } from "@/hooks/usePermission";
import PayrollDashboard from "./_components/PayrollDashboard";
import RunPayrollWizard from "./_components/RunPayrollWizard";
import PayrollReports   from "./_components/PayrollReports";
import PayrollAnalytics from "./_components/PayrollAnalytics";
import SalarySetupTab   from "./_components/SalarySetupTab";

type TabId = "dashboard" | "salary_setup" | "reports" | "analytics";

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: "dashboard",    label: "Dashboard",    icon: "ti-layout-dashboard" },
  { id: "salary_setup", label: "Salary Setup", icon: "ti-currency-rupee"  },
  { id: "reports",      label: "Reports",      icon: "ti-report"           },
  { id: "analytics",    label: "Analytics",    icon: "ti-chart-bar"        },
];

interface ResumeState { cycleId: string; status: string; }

export default function PayrollPage() {
  const canCreate   = usePermission("payroll.create");
  const [active,     setActive]     = useState<TabId>("dashboard");
  const [runWizard,  setRunWizard]  = useState(false);
  const [resume,     setResume]     = useState<ResumeState | null>(null);

  function openFresh() { setResume(null); setRunWizard(true); }
  function openResume(cycleId: string, status: string) { setResume({ cycleId, status }); setRunWizard(true); }
  function closeWizard() { setResume(null); setRunWizard(false); }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Payroll Management</div>
          <div className="page-sub">Process, approve and disburse salaries — {new Date().toLocaleString("en-IN", { month: "long", year: "numeric" })}</div>
        </div>
        {!runWizard && (
          <div className="page-actions">
            <button className="btn btn-ghost btn-sm">
              <i className="ti ti-history" /> View History
            </button>
            {canCreate && (
              <button className="btn btn-filled btn-sm" onClick={openFresh}>
                <i className="ti ti-player-play" /> Run Payroll
              </button>
            )}
          </div>
        )}
      </div>

      {runWizard ? (
        <RunPayrollWizard
          onCancel={closeWizard}
          initialCycleId={resume?.cycleId}
          initialStatus={resume?.status}
        />
      ) : (
        <>
          <div className="tabs">
            {TABS.map(tab => (
              <button
                key={tab.id}
                className={`tab${active === tab.id ? " active" : ""}`}
                onClick={() => setActive(tab.id)}
              >
                <i className={`ti ${tab.icon}`} style={{ marginRight: 5 }} />{tab.label}
              </button>
            ))}
          </div>

          {active === "dashboard"    && <PayrollDashboard onRunPayroll={openFresh} onResumeCycle={openResume} canResume={canCreate} />}
          {active === "salary_setup" && <SalarySetupTab />}
          {active === "reports"      && <PayrollReports />}
          {active === "analytics"    && <PayrollAnalytics />}
        </>
      )}
    </div>
  );
}
