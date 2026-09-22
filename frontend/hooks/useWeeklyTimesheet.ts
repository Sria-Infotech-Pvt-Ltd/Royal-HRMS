import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export interface WeeklyTimesheet {
  hours_logged: number;
  target_hours: number;
  week_start: string;
  week_end: string;
  submitted: boolean;
  submitted_at: string | null;
}

/** Real hours-logged-this-week + submit action for the "Weekly timesheet"
 * card shown on both the ESS Home and Attendance tabs — backed by
 * GET/POST /attendance/my-weekly-timesheet/ (real AttendanceRecord sums and
 * a real WeeklyTimesheetSubmission row, not a fabricated number/no-op). */
export function useWeeklyTimesheet() {
  const { data, loading, refetch } = useFetch<WeeklyTimesheet>(API.attendance.myWeeklyTimesheet);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    try {
      await clientApi.post(API.attendance.myWeeklyTimesheet, {});
      await refetch();
    } finally {
      setSubmitting(false);
    }
  }

  return { data, loading, submitting, submit };
}
