"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { usePermission, useAnyPermission } from "@/hooks/usePermission";
import BranchFilterSelect from "@/components/BranchFilterSelect";
import LeaveDashboard from "./_components/LeaveDashboard";
import LeaveApprovals from "./_components/LeaveApprovals";
import ApplyLeaveForm from "./_components/ApplyLeaveForm";
import TeamCalendar   from "./_components/TeamCalendar";
import LeaveAnalytics from "./_components/LeaveAnalytics";
import AttendanceApprovalTab from "../approvals/_components/AttendanceApprovalTab";
import CorrectionsTab from "../attendance/_components/CorrectionsTab";

interface BranchOption { id: number; branch_name: string }

type TabId = "dashboard" | "apply" | "approvals" | "attendance" | "corrections" | "calendar" | "analytics";

interface Props { role: string }

export default function LeavePageClient({ role }: Props) {
  const isSystemAdmin = role === "system_admin";
  const canApprove    = usePermission("leave.approve");
  // Attendance sign-off lives here only for HR — other roles still use /dashboard/approvals.
  const isHR = role === "hr" || role === "hr_admin";
  const hasAttendanceApprovalPermission = useAnyPermission("payroll.view", "payroll.approve");
  const canApproveAttendance = isHR && hasAttendanceApprovalPermission;
  // Attendance correction (missed-clockout) requests reach HR at the L2 stage —
  // same permission managers use on /dashboard/approvals, HR-scoped here.
  const hasCorrectionPermission = useAnyPermission("attendance.create");
  const canApproveCorrections = isHR && hasCorrectionPermission;

  const ALL_TABS: { id: TabId; label: string }[] = [
    { id: "dashboard",  label: "Dashboard"   },
    { id: "apply",      label: "Apply Leave" },
    ...(canApprove ? [{ id: "approvals" as TabId, label: "Approvals" }] : []),
    ...(canApproveAttendance ? [{ id: "attendance" as TabId, label: "Attendance Approvals" }] : []),
    ...(canApproveCorrections ? [{ id: "corrections" as TabId, label: "Attendance Corrections" }] : []),
    { id: "calendar",   label: "Team Calendar" },
    { id: "analytics",  label: "Analytics"    },
  ];

  const tabs = ALL_TABS;

  const [active, setActive] = useState<TabId>("dashboard");
  const [branch, setBranch] = useState("");

  // Branch filter is system_admin only — HR/manager are already branch-scoped
  // server-side, so they never need to pick one.
  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(
    isSystemAdmin ? `${API.branches.list}?page_size=100` : null
  );
  const branches = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Leave Management</div>
          <div className="page-sub">Apply, approve and track all leave requests</div>
        </div>
        {isSystemAdmin && (
          <BranchFilterSelect branches={branches} value={branch} onChange={setBranch} locked={false} />
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
            branch={branch}
            onApply={() => setActive("apply")}
          />
        )}
        {active === "apply"      && <ApplyLeaveForm onCancel={() => setActive("dashboard")} />}
        {active === "approvals"  && <LeaveApprovals role={role} />}
        {active === "attendance" && canApproveAttendance && <AttendanceApprovalTab />}
        {active === "corrections" && canApproveCorrections && <CorrectionsTab />}
        {active === "calendar"   && <TeamCalendar />}
        {active === "analytics" && <LeaveAnalytics role={role} />}
      </div>
    </div>
  );
}
