import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { WeeklyTimesheetSummary } from "@/types/timesheet";

export type WeeklyTimesheet = WeeklyTimesheetSummary;

/** The one-line summary of this week's timesheet shown on the ESS Home and Attendance cards: attendance hours so far and the
 * real timesheet's state (GET /attendance/my-weekly-timesheet/). Filling and submitting happens on the timesheet page
 * (useTimesheetWeek), which the cards link to. */
export function useWeeklyTimesheet() {
  const { data, loading, refetch } = useFetch<WeeklyTimesheetSummary>(API.attendance.myWeeklyTimesheet);
  return { data, loading, refetch };
}
