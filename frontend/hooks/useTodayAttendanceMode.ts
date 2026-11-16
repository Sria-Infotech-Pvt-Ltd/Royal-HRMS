"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AttendanceMode } from "@/types/attendance";
import type { WorkFromHomeRequest } from "@/types/workFromHome";

// Local calendar date, not UTC (Date.toISOString() would misdate the hours just after local midnight, e.g. 12:30 AM IST is
// still UTC "yesterday" — the exact case an employee clocking in right after midnight would hit).
function localDateString(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function coversToday(request: Pick<WorkFromHomeRequest, "start_date" | "end_date">, now: Date = new Date()): boolean {
  const today = localDateString(now);
  return request.start_date <= today && today <= request.end_date;
}

/**
 * The attendance mode a punch made now should use: "wfh" when today falls inside one of the employee's own approved
 * work-from-home requests, otherwise "office". Every clock-in surface (My Attendance, the ESS home banner, the dashboards)
 * uses this, so a WFH day is checked against the WFH location wherever the employee punches. The server's validation is the
 * real gate; this only decides which validation path a punch goes through.
 */
export function useTodayAttendanceMode(): AttendanceMode {
  const { data } = useFetch<{ results: WorkFromHomeRequest[] }>(`${API.workFromHome.requests}?status=approved&page_size=5`);
  return (data?.results ?? []).some(request => coversToday(request)) ? "wfh" : "office";
}
