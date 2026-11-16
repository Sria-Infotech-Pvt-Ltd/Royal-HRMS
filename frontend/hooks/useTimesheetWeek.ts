"use client";

// One employee-week of the timesheet: read it, save a draft, submit. The server answers a save or a submit with the whole
// refreshed sheet, which replaces what is on screen (so there is no second fetch and totals always come from the server).
// A rejected save or submit keeps what the person typed and lists every problem the server found.

import { useCallback, useState } from "react";
import { useToast } from "@/components/ToastProvider";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { problemsFromError } from "@/lib/timesheet";
import type { TimesheetSavePayload, TimesheetWeekView } from "@/types/timesheet";

interface Answered {
  week: string;
  view: TimesheetWeekView;
}

interface Envelope {
  data: TimesheetWeekView;
  message?: string;
}

export function useTimesheetWeek(week: string) {
  const { showToast } = useToast();
  const { data, loading, error, refetch } = useFetch<TimesheetWeekView>(API.attendance.timesheets.myWeekView(week));
  const [answered, setAnswered] = useState<Answered | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  // While a different week is loading, useFetch still holds the previous one: never show it under the new week's heading.
  const fetched = data && data.week_start === week ? data : null;
  const view = answered && answered.week === week ? answered.view : fetched;

  const run = useCallback(async (call: () => Promise<{ data: Envelope }>, fallback: string, success: string): Promise<boolean> => {
    setProblems([]);
    try {
      const response = await call();
      setAnswered({ week, view: response.data.data });
      showToast(success, "success");
      return true;
    } catch (caught: unknown) {
      setProblems(problemsFromError(caught, fallback));
      return false;
    }
  }, [week, showToast]);

  const save = useCallback(async (payload: TimesheetSavePayload): Promise<boolean> => {
    setIsSaving(true);
    try {
      return await run(() => clientApi.put<Envelope>(API.attendance.timesheets.myWeek(week), payload), "Could not save the timesheet.", "Timesheet saved.");
    } finally {
      setIsSaving(false);
    }
  }, [run, week]);

  const submit = useCallback(async (): Promise<boolean> => {
    setIsSubmitting(true);
    try {
      return await run(() => clientApi.post<Envelope>(API.attendance.timesheets.mySubmit(week), {}), "Could not submit the timesheet.", "Timesheet submitted for approval.");
    } finally {
      setIsSubmitting(false);
    }
  }, [run, week]);

  const clearProblems = useCallback(() => setProblems([]), []);

  return { view, loading: loading && !view, error, refetch, save, submit, isSaving, isSubmitting, problems, clearProblems };
}
