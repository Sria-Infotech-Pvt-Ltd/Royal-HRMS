"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AttendanceStats, MonthlySummary, CalendarResponse, DayRecord, HistoryRow } from "@/types/attendance";

export function useAttendanceDashboard({ month, year }: { month: number; year: number }) {
  const statsUrl    = `${API.attendance.stats}?month=${month}&year=${year}`;
  const summaryUrl  = `${API.attendance.summary}?month=${month}&year=${year}`;
  const calendarUrl = `${API.attendance.calendar}?month=${month}&year=${year}`;

  const { data: stats,   loading: statsLoading,   error: statsError,   refetch: refetchStats   } = useFetch<AttendanceStats>(statsUrl);
  const { data: summary, loading: summaryLoading, error: summaryError, refetch: refetchSummary } = useFetch<MonthlySummary>(summaryUrl);
  const { data: calData, loading: calLoading,     error: calError,     refetch: refetchCal     } = useFetch<CalendarResponse>(calendarUrl);

  function refetch() {
    refetchStats();
    refetchSummary();
    refetchCal();
  }

  const calendar: Record<string, DayRecord> = calData?.calendar?.days ?? {};
  const history: HistoryRow[] = calData?.history ?? [];

  return {
    stats,
    summary,
    calendar,
    history,
    isLoading: statsLoading || summaryLoading || calLoading,
    error: statsError ?? summaryError ?? calError ?? null,
    refetch,
  };
}
