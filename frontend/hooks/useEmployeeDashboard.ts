import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type {
  EmployeeKPIs,
  LeaveBalanceSummary,
  ActionItemsResponse,
  RecentRequestsResponse,
  AttendanceSummary,
  AttendanceStatus,
  Announcement,
} from "@/types/employeeDashboard";
import type { HRBirthdayEmployee } from "@/types/dashboard";

export const useEmployeeKPIs = () =>
  useFetch<EmployeeKPIs>(API.employeeDashboard.kpis);

export const useLeaveBalances = (year?: number) =>
  useFetch<LeaveBalanceSummary>(
    year
      ? `${API.employeeDashboard.leaveBalances}?year=${year}`
      : API.employeeDashboard.leaveBalances
  );

export const useActionItems = () =>
  useFetch<ActionItemsResponse>(API.employeeDashboard.actionItems);

export const useRecentRequests = () =>
  useFetch<RecentRequestsResponse>(API.employeeDashboard.recentRequests);

export const useAttendanceSummary = (month?: number, year?: number) =>
  useFetch<AttendanceSummary>(
    month && year
      ? `${API.employeeDashboard.attendanceSummary}?month=${month}&year=${year}`
      : API.employeeDashboard.attendanceSummary
  );

export const useAttendanceStatus = () =>
  useFetch<AttendanceStatus>(API.employeeDashboard.attendanceStatus);

export const useSharedAnnouncement = () =>
  useFetch<Announcement | null>(API.employeeDashboard.announcement);

export const useBirthdaysToday = () =>
  useFetch<HRBirthdayEmployee[]>(API.employeeDashboard.birthdaysToday);
