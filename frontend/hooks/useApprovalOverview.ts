"use client";

import { useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import { summariseTeamApprovals, type KindCount } from "@/lib/approvalOverview";
import type { PaginatedFaceRegistrations } from "@/types/faceRegistration";
import {
  correctionToItem, expenseToItem, leaveToItem, separationToItem, wfhToItem,
  type ApprovalItem, type ApprovalKind, type CorrectionListResponse, type ExpenseListResponse, type LeaveListResponse,
  type SeparationListResponse, type WfhListResponse,
} from "@/app/dashboard/approvals/_data";

interface Options {
  /** The user can see Team Approvals (leave / WFH / expenses / regularization / separation). */
  includeTeam: boolean;
  /** The user can approve Face ID registrations. */
  includeFace: boolean;
}

export interface ApprovalOverview {
  team: KindCount[];
  /** Every approval row the person can see, for callers that need more than counts (for example "this month"). */
  items: ApprovalItem[];
  faceVisible: number;
  faceAssignedToMe: number;
  isLoading: boolean;
}

/**
 * Counts for My Approvals. Each count comes from the workflow's own list endpoint, which the server already limits to
 * what the signed-in user may see; nothing is fetched for a workflow the user cannot approve.
 */
export function useApprovalOverview({ includeTeam, includeFace }: Options): ApprovalOverview {
  // Each workflow is requested only when the person may approve it: without that permission its list endpoint answers with
  // the person's OWN requests, which must not be counted as "waiting for me".
  const mayLeave = usePermission("leave.approve");
  const mayWfh = usePermission("wfh.approve");
  const mayExpense = usePermission("expenses.approve");
  const mayCorrection = usePermission("attendance.view");   // the corrections list itself needs attendance.view
  const maySeparation = usePermission("separation.approve");
  const team = (url: string, isAllowed: boolean) => (includeTeam && isAllowed ? url : null);
  const leave = useFetch<LeaveListResponse>(team(`${API.approvals.leaveRequests}?scope=team&page_size=100`, mayLeave));
  const wfh = useFetch<WfhListResponse>(team(`${API.approvals.wfhRequests}?scope=team&page_size=100`, mayWfh));
  const expense = useFetch<ExpenseListResponse>(team(`${API.approvals.expenseList}?page_size=100`, mayExpense));
  const correction = useFetch<CorrectionListResponse>(team(`${API.attendance.corrections}?page_size=100`, mayCorrection));
  const separation = useFetch<SeparationListResponse>(team(`${API.separation.list}?scope=team&page_size=100`, maySeparation));
  const approvable: ApprovalKind[] = [
    ...(mayLeave ? ["leave" as const] : []), ...(mayWfh ? ["wfh" as const] : []), ...(mayExpense ? ["expense" as const] : []),
    ...(mayCorrection ? ["attendance_correction" as const] : []), ...(maySeparation ? ["separation" as const] : []),
  ];

  const face = (suffix: string) => (includeFace ? `${API.attendance.faceRegistration.pending}?page_size=1${suffix}` : null);
  const faceAll = useFetch<PaginatedFaceRegistrations>(face(""));
  const faceMine = useFetch<PaginatedFaceRegistrations>(face("&assigned_to_me=1"));

  const items: ApprovalItem[] = useMemo(() => [
    ...(leave.data?.results ?? []).map(leaveToItem),
    ...(wfh.data?.results ?? []).map(wfhToItem),
    ...(expense.data?.results ?? []).map(expenseToItem),
    ...(correction.data?.results ?? []).map(correctionToItem),
    ...(separation.data?.results ?? []).map(separationToItem),
  ], [leave.data, wfh.data, expense.data, correction.data, separation.data]);

  return {
    team: includeTeam ? summariseTeamApprovals(items, approvable) : [],
    items,
    faceVisible: faceAll.data?.count ?? 0,
    faceAssignedToMe: faceMine.data?.count ?? 0,
    isLoading: [leave, wfh, expense, correction, separation, faceAll, faceMine].some(request => request.loading),
  };
}
