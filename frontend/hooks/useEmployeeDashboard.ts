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
  BirthdaysTodayResponse,
  MyBirthdayWidgets,
} from "@/types/employeeDashboard";

export const useEmployeeKPIs = () =>
  useFetch<EmployeeKPIs>(API.employeeDashboard.kpis);

export const useLeaveBalances = (year?: number) =>
  useFetch<LeaveBalanceSummary>(
    year
      ? `${API.employeeDashboard.leaveBalances}?year=${year}`
      : API.employeeDashboard.leaveBalances
  );

export const useActionItems = (page: number = 1, pageSize: number = 5) =>
  useFetch<ActionItemsResponse>(
    `${API.employeeDashboard.actionItems}?page=${page}&page_size=${pageSize}`
  );

export const useRecentRequests = (page: number = 1, pageSize: number = 5) =>
  useFetch<RecentRequestsResponse>(
    `${API.employeeDashboard.recentRequests}?page=${page}&page_size=${pageSize}`
  );

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
  useFetch<BirthdaysTodayResponse>(API.employeeDashboard.birthdaysToday);

export const useMyBirthdayWidgets = () =>
  useFetch<MyBirthdayWidgets>(API.employeeDashboard.myBirthdayWidgets);
