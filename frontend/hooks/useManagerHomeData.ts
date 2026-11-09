"use client";

import { useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useAnyPermission } from "@/hooks/usePermission";
import { useApprovalOverview } from "@/hooks/useApprovalOverview";
import { API } from "@/lib/api/endpoints";
import type { KindCount } from "@/lib/approvalOverview";
import { teamBreakdown, waitingThisMonth, type TeamBreakdown } from "@/lib/managerHome";
import type { ApprovalKind } from "@/app/dashboard/approvals/_data";
import type { ManagerActivityEntry, ManagerDashboardData } from "@/types/managerDashboard";

export interface ManagerHomeData {
  breakdown: TeamBreakdown;
  team: KindCount[];
  waitingThisMonth: Record<ApprovalKind, number>;
  activity: ManagerActivityEntry[];
  isLoading: boolean;
  error: string | null;
}

/**
 * Everything the Manager dashboard shows, from the existing manager endpoint (a manager's own direct reports only) and
 * each approval workflow's own scoped list. Workflows the manager may not approve are never requested or shown.
 */
export function useManagerHomeData(now: Date | null): ManagerHomeData {
  const manager = useFetch<ManagerDashboardData>(API.dashboard.manager);
  const canApprove = useAnyPermission("leave.approve", "expenses.approve", "attendance.create", "separation.approve", "wfh.approve");
  const approvals = useApprovalOverview({ includeTeam: canApprove, includeFace: false });

  const breakdown = useMemo(() => teamBreakdown(manager.data?.team_attendance ?? []), [manager.data]);
  const monthly = useMemo(() => waitingThisMonth(approvals.items, now ?? new Date(0)), [approvals.items, now]);

  return {
    breakdown, team: approvals.team, waitingThisMonth: monthly,
    activity: manager.data?.recent_team_activity ?? [],
    isLoading: manager.loading || approvals.isLoading, error: manager.error,
  };
}
