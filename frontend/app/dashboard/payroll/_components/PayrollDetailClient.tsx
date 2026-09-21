"use client";

import { useState } from "react";
import { usePermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import PayrollDashboard   from "./PayrollDashboard";
import RunPayrollWizard   from "./RunPayrollWizard";
import BranchStatusOverview from "./BranchStatusOverview";
import PayrollReports     from "./PayrollReports";
import PayrollAnalytics   from "./PayrollAnalytics";
import SalarySetupTab     from "./SalarySetupTab";
import PayrollAdjustments from "./PayrollAdjustments";

type TabId = "dashboard" | "salary_setup" | "adjustments" | "reports" | "analytics";

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: "dashboard",    label: "Dashboard",    icon: "ti-layout-dashboard" },
  { id: "salary_setup", label: "Salary Setup", icon: "ti-currency-rupee"   },
  { id: "adjustments",  label: "Adjustments",  icon: "ti-adjustments-alt"  },
  { id: "reports",      label: "Reports",      icon: "ti-report"            },
  { id: "analytics",    label: "Analytics",    icon: "ti-chart-bar"         },
];

interface ResumeState { cycleId: string; status: string; cycleStart?: string; }
interface BranchWizardState { branchId?: string; branchName?: string; }

export default function PayrollDetailClient({ initialTab, onBack }: { initialTab?: TabId; onBack: () => void }) {
  const canCreate = usePermission("payroll.create");
  const user      = useCurrentUser();

  const isAdmin = user?.is_superuser === true;
  const userBranch = user?.branch ?? "";

  const [active,    setActive]    = useState<TabId>(initialTab ?? "dashboard");
  const [runWizard, setRunWizard] = useState(false);
  const [resume,    setResume]    = useState<ResumeState | null>(null);
  const [branchWizard, setBranchWizard] = useState<BranchWizardState>({});
  const [pendingPeriod, setPendingPeriod] = useState<{ month?: string; year?: string }>({});

  /** Admin opens wizard for a specific branch. */
  function openForBranch(branchId: string, branchName: string) {
    setResume(null);
    setBranchWizard({ branchId, branchName });
    setPendingPeriod({});
    setRunWizard(true);
  }

  /** HR opens wizard for their own branch. month/year are set when opened
   * from the payroll calendar's "Run {month} Payroll" button. */
  function openFresh(month?: string, year?: string) {
    setResume(null);
    setBranchWizard({});
    setPendingPeriod({ month, year });
    setRunWizard(true);
  }

  function openResume(cycleId: string, status: string, cycleStart?: string) {
    setResume({ cycleId, status, cycleStart });
    setBranchWizard({});
    setPendingPeriod({});
    setRunWizard(true);
  }

  function closeWizard() {
    setResume(null);
    setBranchWizard({});
    setPendingPeriod({});
    setRunWizard(false);
  }

  // Build wizard props depending on role
  const wizardProps = isAdmin
    ? {
        isAdmin: true as const,
        initialBranchId: branchWizard.branchId,
        initialMonth: pendingPeriod.month,
        initialYear: pendingPeriod.year,
      }
    : {
        lockedBranch: userBranch
          ? { id: "", name: userBranch }  // id resolved server-side via user.branch
          : undefined,
        initialMonth: pendingPeriod.month,
        initialYear: pendingPeriod.year,
      };

  return (
    <div>
      <div className="page-header">
        <div>
          <button
            onClick={onBack}
            style={{ display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", color: "var(--primary)", fontSize: 12.5, fontWeight: 700, cursor: "pointer", padding: 0, marginBottom: 8 }}
          >
            <i className="ti ti-arrow-left" /> Back to overview
          </button>
          <div className="page-title">Payroll Management</div>
          <div className="page-sub">
            Process, approve and disburse salaries —{" "}
            {(runWizard && resume?.cycleStart
              ? new Date(resume.cycleStart)
              : new Date()
            ).toLocaleString("en-IN", { month: "long", year: "numeric" })}
            {!isAdmin && userBranch && (
              <span style={{ marginLeft: 10, fontSize: 12, color: "var(--primary)", fontWeight: 600 }}>
                <i className="ti ti-building" style={{ marginRight: 4 }} />{userBranch}
              </span>
            )}
          </div>
        </div>
        {!runWizard && (
          <div className="page-actions">
            {canCreate && (
              <button className="btn btn-filled btn-sm" onClick={() => openFresh()}>
                <i className="ti ti-player-play" />
                {isAdmin ? "Run Payroll" : `Run Payroll — ${userBranch}`}
              </button>
            )}
          </div>
        )}
      </div>

      {/* HR: no branch assigned warning */}
      {!isAdmin && !userBranch && !runWizard && (
        <div className="alert alert-warn" style={{ marginBottom: 20 }}>
          <i className="ti ti-alert-triangle" />
          <span>
            Your account is not assigned to a branch. Payroll actions are unavailable until an
            administrator assigns you to a branch in Settings → Employees.
          </span>
        </div>
      )}

      {runWizard ? (
        <RunPayrollWizard
          onCancel={closeWizard}
          initialCycleId={resume?.cycleId}
          initialStatus={resume?.status}
          {...wizardProps}
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

          {active === "dashboard" && (
            <>
              {/* Admin sees every branch; branch-scoped users (branch_admin, HR) see only
                  their own branch — the backend scopes the response accordingly. */}
              {(isAdmin || userBranch) && (
                <BranchStatusOverview
                  onRunBranch={openForBranch}
                  onResumeBranch={openResume}
                />
              )}
              <PayrollDashboard
                onRunPayroll={openFresh}
                onResumeCycle={openResume}
                canResume={canCreate}
              />
            </>
          )}
          {active === "salary_setup" && <SalarySetupTab />}
          {active === "adjustments"  && <PayrollAdjustments />}
          {active === "reports"      && <PayrollReports />}
          {active === "analytics"    && <PayrollAnalytics />}
        </>
      )}
    </div>
  );
}
