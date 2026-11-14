"use client";

// The approver's side of timesheets: the queue (paginated, filtered by status) and the count of sheets waiting for this person.
// The server returns only the sheets this person may decide, so there is nothing to filter by permission on the screen.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { TimesheetStatus, TimesheetTeamPage } from "@/types/timesheet";

export type QueueFilter = TimesheetStatus | "all";

export const QUEUE_PAGE_SIZE = 20;

/** "all" asks for everything the person can see except drafts, which the server never shows to anyone but their owner. */
export function queueUrl(filter: QueueFilter, page: number): string {
  const status = filter === "all" ? "" : `status=${filter}&`;
  return `${API.attendance.timesheets.team}?${status}page=${page}&page_size=${QUEUE_PAGE_SIZE}`;
}

export function useTimesheetQueue(filter: QueueFilter, page: number) {
  const { data, loading, error, refetch } = useFetch<TimesheetTeamPage>(queueUrl(filter, page));
  return { page: data, loading, error, refetch };
}

/** How many submitted timesheets are waiting for this person; null while loading or when not asked for. */
export function useTimesheetPending(isEnabled: boolean): number | null {
  const { data } = useFetch<TimesheetTeamPage>(isEnabled ? `${API.attendance.timesheets.team}?status=submitted&page_size=1` : null);
  return data ? data.pending_count : null;
}
