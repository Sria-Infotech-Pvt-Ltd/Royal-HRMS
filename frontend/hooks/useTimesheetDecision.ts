"use client";

// Opening one submitted timesheet and deciding it: approve, send back (reason required), or - for HR - unlock an approved one.
// Every action answers with the refreshed sheet, which replaces what the drawer shows; a refused action keeps the sheet and
// reports why (for example "already approved by someone else").

import { useCallback, useState } from "react";
import { useToast } from "@/components/ToastProvider";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { problemsFromError } from "@/lib/timesheet";
import type { TimesheetWeekView } from "@/types/timesheet";

interface Envelope {
  data: TimesheetWeekView;
}

interface Answered {
  id: string;
  view: TimesheetWeekView;
}

export function useTimesheetDecision(timesheetId: string | null, onChanged: () => void) {
  const { showToast } = useToast();
  const { data, loading, error } = useFetch<TimesheetWeekView>(timesheetId ? API.attendance.timesheets.detail(timesheetId) : null);
  const [answered, setAnswered] = useState<Answered | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [problem, setProblem] = useState("");

  const view = timesheetId && answered?.id === timesheetId ? answered.view : data;

  const act = useCallback(async (url: string, body: { reason?: string }, done: string): Promise<boolean> => {
    if (!timesheetId) return false;
    setIsBusy(true);
    setProblem("");
    try {
      const response = await clientApi.post<Envelope>(url, body);
      setAnswered({ id: timesheetId, view: response.data.data });
      showToast(done, "success");
      onChanged();
      return true;
    } catch (caught: unknown) {
      setProblem(problemsFromError(caught, "That did not go through. Please try again.")[0]);
      return false;
    } finally {
      setIsBusy(false);
    }
  }, [timesheetId, onChanged, showToast]);

  const approve = useCallback(() => act(timesheetId ? API.attendance.timesheets.approve(timesheetId) : "", {}, "Timesheet approved."), [act, timesheetId]);
  const sendBack = useCallback((reason: string) => act(timesheetId ? API.attendance.timesheets.returnBack(timesheetId) : "", { reason }, "Timesheet sent back to the employee."), [act, timesheetId]);
  const unlock = useCallback((reason: string) => act(timesheetId ? API.attendance.timesheets.unlock(timesheetId) : "", { reason }, "Timesheet reopened for correction."), [act, timesheetId]);
  const clearProblem = useCallback(() => setProblem(""), []);

  return { view, loading: loading && !view, error, isBusy, problem, clearProblem, approve, sendBack, unlock };
}
