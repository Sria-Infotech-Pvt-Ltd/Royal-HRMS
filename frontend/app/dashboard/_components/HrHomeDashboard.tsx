"use client";

// The dedicated HR dashboard (/dashboard/hr). HR users also have the employee-style workspace at /dashboard/ess; this
// is a separate screen. Every figure comes from existing authorized APIs (see hooks/useHrHomeData); a figure with no
// source is a dash. The cards only link to pages whose own route guards and APIs still decide access.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import HrQuickActionsCard, { type HrQuickAction } from "@/components/dashboard/hrhome/HrQuickActionsCard";
import { HrHomeBanner, HrHomeTiles } from "@/components/dashboard/hrhome/HrHomeHeader";
import {
  HrPendingRequestsCard, HrPipelineCard, HrRecentActivitiesCard, HrTeamComplianceCard,
} from "@/components/dashboard/hrhome/HrHomeCards";
import styles from "@/components/dashboard/hrhome/hrHome.module.css";
import { useHrHomeData } from "@/hooks/useHrHomeData";
import { useAnyPermission, usePermission } from "@/hooks/usePermission";
import type { SessionPayload } from "@/lib/session";

export default function HrHomeDashboard({ session }: { session: SessionPayload }) {
  const router = useRouter();
  const data = useHrHomeData();
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);

  const canHire = usePermission("employees.create");
  const canAddCandidate = usePermission("recruitment.create");
  const canSeeRecruitment = usePermission("recruitment.view");
  const canReviewOnboarding = useAnyPermission("recruitment.view", "onboarding.approve");
  const canApprove = useAnyPermission(
    "leave.approve", "expenses.approve", "payroll.edit", "employees.approve", "employees.raise_action", "facial_recognition.approve",
  );

  const go = (path: string) => () => router.push(path);
  const actions: HrQuickAction[] = [
    canSeeRecruitment && { key: "interviews", label: "Interview List", icon: "ti-list-details", onClick: go("/dashboard/interview-list") },
    canHire && { key: "hire", label: "Register Employee", icon: "ti-user-plus", onClick: go("/dashboard/employees?action=hire") },
    canApprove && { key: "approve", label: "Approve Requests", icon: "ti-circle-check", onClick: go("/dashboard/approvals") },
    canAddCandidate && { key: "candidate", label: "Add Candidate", icon: "ti-user-search", onClick: go("/dashboard/interview-list?action=add") },
    canReviewOnboarding && { key: "onboarding", label: "Assign Onboarding", icon: "ti-clipboard-check", onClick: go("/dashboard/candidate-review?tab=onboarding") },
    { key: "reports", label: "Generate Reports", icon: "ti-chart-bar", onClick: go("/dashboard/reports") },
  ].filter((action): action is HrQuickAction => Boolean(action));

  return (
    <div className={styles.page}>
      <HrHomeBanner name={session.name} designation={session.designation} now={now} onOpenWorkspace={go("/dashboard/ess")} />
      <HrHomeTiles
        overview={data.overview} pipeline={data.pipeline} isLoading={data.isOverviewLoading || data.isApprovalsLoading}
        pendingApprovals={data.pendingRows.length > 0 ? data.pendingApprovals : null}
      />
      <div className={styles.grid3}>
        <HrPendingRequestsCard rows={data.pendingRows} isLoading={data.isApprovalsLoading} onOpen={go("/dashboard/approvals")} />
        <HrPipelineCard pipeline={data.pipeline} onOpen={go("/dashboard/interview-list")} />
        <HrQuickActionsCard actions={actions} />
        <HrRecentActivitiesCard activities={data.activities} now={now} isLoading={data.isActivitiesLoading} />
        <HrTeamComplianceCard attendanceExceptions={data.overview?.attendance_exceptions_today ?? null} onOpenAttendance={go("/dashboard/attendance")} />
      </div>
    </div>
  );
}
