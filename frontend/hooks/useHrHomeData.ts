"use client";

import { useFetch } from "@/hooks/useFetch";
import { useAnyPermission, usePermission } from "@/hooks/usePermission";
import { useApprovalOverview } from "@/hooks/useApprovalOverview";
import { useDashboardOverview } from "@/hooks/useDashboardOverview";
import { API } from "@/lib/api/endpoints";
import { pendingApprovalsForMe, pendingRequestRows, type PendingRequestRow } from "@/lib/hrHome";
import type { DashboardOverview } from "@/types/dashboard";
import type { NotificationListResponse } from "@/types/notifications";

interface CountPage {
  count: number;
}

export interface PipelineCounts {
  applications: number | null;
  screening: number | null;
  interviews: number | null;
  offerStage: number | null;
}

export interface HrHomeData {
  overview: DashboardOverview | null;
  isOverviewLoading: boolean;
  pendingRows: PendingRequestRow[];
  pendingApprovals: number;
  isApprovalsLoading: boolean;
  pipeline: PipelineCounts;
  activities: NotificationListResponse["results"];
  isActivitiesLoading: boolean;
}

/**
 * Everything the HR dashboard shows, from existing authorized APIs: the HR overview, each workflow's own scoped
 * approval list, the candidate list per stage, and the person's own notifications. A source the viewer is not allowed
 * to read is never requested, and its value stays null (shown as a dash).
 */
export function useHrHomeData(): HrHomeData {
  const overview = useDashboardOverview();

  const canApproveTeam = useAnyPermission("leave.approve", "expenses.approve", "attendance.create", "separation.approve");
  const canApproveFace = usePermission("facial_recognition.approve");
  const approvals = useApprovalOverview({ includeTeam: canApproveTeam, includeFace: canApproveFace });
  const input = { team: canApproveTeam ? approvals.team : null, face: canApproveFace ? approvals.faceVisible : null };

  // Candidate stages: the candidate list filtered by status, one request each, reading only the total.
  const canSeeRecruitment = usePermission("recruitment.view");
  const stage = (status: string) => (canSeeRecruitment ? `${API.recruitment.candidates}?page_size=1${status ? `&status=${status}` : ""}` : null);
  const applications = useFetch<CountPage>(stage(""));
  const screening = useFetch<CountPage>(stage("screening"));
  const interviews = useFetch<CountPage>(stage("interview_scheduled"));
  const selected = useFetch<CountPage>(stage("selected"));
  const offerSent = useFetch<CountPage>(stage("offer_sent"));
  const offerStage = selected.data && offerSent.data ? selected.data.count + offerSent.data.count : null;

  const notifications = useFetch<NotificationListResponse>(`${API.notifications.list}?page_size=3`);

  return {
    overview: overview.data,
    isOverviewLoading: overview.loading,
    pendingRows: pendingRequestRows(input),
    pendingApprovals: pendingApprovalsForMe(input),
    isApprovalsLoading: approvals.isLoading,
    pipeline: {
      applications: applications.data?.count ?? null,
      screening: screening.data?.count ?? null,
      interviews: interviews.data?.count ?? null,
      offerStage,
    },
    activities: notifications.data?.results ?? [],
    isActivitiesLoading: notifications.loading,
  };
}
