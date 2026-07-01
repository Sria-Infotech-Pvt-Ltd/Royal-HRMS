"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AttendanceStats, AttendanceSummary } from "@/types/myAttendance";

export function useMyAttendance() {
  const now = new Date();
  // Month is 1-indexed (API format: January = 1)
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year,  setYear]  = useState(now.getFullYear());

  const statsUrl   = `${API.attendance.stats}?month=${month}&year=${year}`;
  const summaryUrl = `${API.attendance.summary}?month=${month}&year=${year}`;

  const { data: stats,   loading: statsLoading,   error: statsError   } = useFetch<AttendanceStats>(statsUrl);
  const { data: summary, loading: summaryLoading, error: summaryError } = useFetch<AttendanceSummary>(summaryUrl);

  function prev() {
    if (month === 1) { setMonth(12); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  }

  function next() {
    if (month === 12) { setMonth(1); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  }

  return {
    month,
    year,
    prev,
    next,
    stats,
    summary,
    loading: statsLoading || summaryLoading,
    error:   statsError ?? summaryError ?? null,
  };
}
