"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AttendanceStats, MonthlySummary, CalendarResponse, DayRecord, HistoryRow } from "@/types/attendance";

export function useEmployeeAttendance(employeeId: string) {
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year,  setYear]  = useState(now.getFullYear());

  const empParam    = `employee_id=${encodeURIComponent(employeeId)}`;
  const statsUrl    = `${API.attendance.stats}?${empParam}&month=${month}&year=${year}`;
  const summaryUrl  = `${API.attendance.summary}?${empParam}&month=${month}&year=${year}`;
  const calendarUrl = `${API.attendance.calendar}?${empParam}&month=${month}&year=${year}`;

  const { data: stats,   loading: statsLoading,   error: statsError   } = useFetch<AttendanceStats>(statsUrl);
  const { data: summary, loading: summaryLoading, error: summaryError } = useFetch<MonthlySummary>(summaryUrl);
  const { data: calData, loading: calLoading,     error: calError     } = useFetch<CalendarResponse>(calendarUrl);

  function prev() {
    if (month === 1) { setMonth(12); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  }

  function next() {
    if (month === 12) { setMonth(1); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  }

  const calendar: Record<string, DayRecord> = calData?.calendar?.days ?? {};
  const history: HistoryRow[] = calData?.history ?? [];

  return {
    month,
    year,
    prev,
    next,
    stats,
    summary,
    calendar,
    history,
    loading: statsLoading || summaryLoading || calLoading,
    error:   statsError ?? summaryError ?? calError ?? null,
  };
}
