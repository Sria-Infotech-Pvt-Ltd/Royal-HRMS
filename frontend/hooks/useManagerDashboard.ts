import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type {
  ManagerKPIs,
  PendingApprovalsResponse,
  TeamAttendanceResponse,
  UpcomingLeaveResponse,
  RecentActivityResponse,
} from "@/types/managerDashboard";

export const useManagerKPIs = () =>
  useFetch<ManagerKPIs>(API.managerDashboard.kpis);

export const useManagerPendingApprovals = () =>
  useFetch<PendingApprovalsResponse>(API.managerDashboard.pendingApprovals);

export const useTeamAttendanceToday = () =>
  useFetch<TeamAttendanceResponse>(API.managerDashboard.teamAttendance);

export const useUpcomingTeamLeave = () =>
  useFetch<UpcomingLeaveResponse>(API.managerDashboard.upcomingLeave);

export const useRecentTeamActivity = () =>
  useFetch<RecentActivityResponse>(API.managerDashboard.recentActivity);
