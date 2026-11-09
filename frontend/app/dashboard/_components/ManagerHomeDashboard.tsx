"use client";

// The dedicated Manager dashboard (/dashboard/team). Managers also have the employee-style workspace at /dashboard/ess;
// this is a separate screen. Every figure comes from the existing manager endpoint (the manager's own direct reports) and
// each approval workflow's own scoped list; a figure with no source is a dash. Buttons only link to pages whose route
// guards and APIs still decide access.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import HrQuickActionsCard, { type HrQuickAction } from "@/components/dashboard/hrhome/HrQuickActionsCard";
import { HrHomeBanner, StatTiles, type StatTile } from "@/components/dashboard/hrhome/HrHomeHeader";
import {
  PendingTeamApprovalsCard, RecentTeamActivityCard, TeamOverviewCard, TeamRequestsMonthCard,
} from "@/components/dashboard/managerhome/ManagerHomeCards";
import styles from "@/components/dashboard/hrhome/hrHome.module.css";
import { useManagerHomeData } from "@/hooks/useManagerHomeData";
import { useAnyPermission, usePermission } from "@/hooks/usePermission";
import { pendingFor, teamApprovalRows, totalTeamPending } from "@/lib/managerHome";
import type { SessionPayload } from "@/lib/session";

export default function ManagerHomeDashboard({ session }: { session: SessionPayload }) {
  const router = useRouter();
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);
  const data = useManagerHomeData(now);

  const canApprove = useAnyPermission("leave.approve", "expenses.approve", "attendance.create", "separation.approve", "wfh.approve");
  const canSeeAttendance = usePermission("attendance.view");
  const canSeeTeam = usePermission("employees.view");
  const canSeeReports = useAnyPermission(
    "reports.view", "employees.export", "attendance.view", "leave.approve", "wfh.approve", "separation.approve",
    "facial_recognition.approve", "recruitment.view",
  );

  const go = (path: string) => () => router.push(path);
  const rows = teamApprovalRows(data.team);
  const tiles: StatTile[] = [
    { key: "members", label: "Team Members", icon: "ti-users", value: data.breakdown.total },
    { key: "pending", label: "Pending Approvals", icon: "ti-file-text", value: data.team.length > 0 ? totalTeamPending(rows) : null },
    { key: "leave", label: "Leave Requests", icon: "ti-calendar-event", value: pendingFor(data.team, "leave") },
    { key: "wfh", label: "WFH Requests", icon: "ti-home-2", value: pendingFor(data.team, "wfh") },
    { key: "expense", label: "Expense Requests", icon: "ti-wallet", value: pendingFor(data.team, "expense") },
    { key: "correction", label: "Attendance Regularization", icon: "ti-clock-edit", value: pendingFor(data.team, "attendance_correction") },
  ];
  const actions: HrQuickAction[] = [
    canApprove && { key: "approve", label: "Approve Requests", icon: "ti-circle-check", onClick: go("/dashboard/approvals") },
    canSeeAttendance && { key: "attendance", label: "Team Attendance", icon: "ti-calendar-check", onClick: go("/dashboard/attendance") },
    canSeeReports && { key: "reports", label: "Team Reports", icon: "ti-chart-bar", onClick: go("/dashboard/reports") },
    canSeeTeam && { key: "team", label: "View Team", icon: "ti-users", onClick: go("/dashboard/employees") },
  ].filter((action): action is HrQuickAction => Boolean(action));

  return (
    <div className={styles.page}>
      <HrHomeBanner title="Manager Dashboard" name={session.name} designation={session.designation} now={now} onOpenWorkspace={go("/dashboard/ess")} />
      <StatTiles tiles={tiles} isLoading={data.isLoading} />
      {data.error && <p role="alert" style={{ color: "var(--error)", margin: 0 }}>{data.error}</p>}
      <div className={styles.grid3}>
        <TeamOverviewCard breakdown={data.breakdown} isLoading={data.isLoading} onOpenTeam={canSeeTeam ? go("/dashboard/employees") : null} />
        <PendingTeamApprovalsCard rows={rows} isLoading={data.isLoading} onOpen={go("/dashboard/approvals")} />
        <HrQuickActionsCard actions={actions} />
        <RecentTeamActivityCard activity={data.activity} now={now} isLoading={data.isLoading} />
        <TeamRequestsMonthCard counts={data.waitingThisMonth} kinds={data.team.map(count => count.kind)} />
      </div>
    </div>
  );
}
