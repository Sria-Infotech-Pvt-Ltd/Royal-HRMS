// Pure helpers for the Onboarding Approvals page: no component state, safe to import anywhere.

import type { QueueCounts, QueueStatus } from "@/types/onboardingQueue";

/** How each queue status reads on screen. Anything else the server might send shows as a neutral "Pending". */
export const STATUS_META: Record<QueueStatus, { label: string; badge: string; icon: string }> = {
  submitted: { label: "Awaiting review", badge: "badge-warn",  icon: "ti-eye" },
  rejected:  { label: "Needs revision",  badge: "badge-error", icon: "ti-refresh" },
  approved:  { label: "Approved",        badge: "badge-success", icon: "ti-check" },
};
export const FALLBACK_STATUS = { label: "Pending", badge: "badge-neutral", icon: "ti-clock" };

/** The server stores an approved person's status as "complete", while the filter word for them is "approved". */
export function isApprovedStatus(status: string): boolean {
  return status === "complete" || status === "approved";
}

export function statusMeta(status: string) {
  if (isApprovedStatus(status)) return STATUS_META.approved;
  return STATUS_META[status as QueueStatus] ?? FALLBACK_STATUS;
}

export interface ApprovalCardSpec { key: "" | QueueStatus; label: string; value: number; icon: string; tone: string; sub: string }

/** The summary cards: everyone, those waiting for review, those sent back, and those already approved. */
export function buildApprovalCards(counts: QueueCounts): ApprovalCardSpec[] {
  return [
    { key: "",          label: "All submissions", value: counts.total,     icon: "ti-users",   tone: "si-primary", sub: counts.total === 0 ? "No submissions yet" : "Everyone who used the onboarding wizard" },
    { key: "submitted", label: "Awaiting review", value: counts.submitted, icon: "ti-eye",     tone: "si-warn",    sub: counts.submitted === 0 ? "Nothing waiting for you" : "Waiting for your review" },
    { key: "rejected",  label: "Needs revision",  value: counts.rejected,  icon: "ti-refresh", tone: "si-error",   sub: counts.rejected === 0 ? "Nobody sent back" : "Waiting for the employee to resubmit" },
    { key: "approved",  label: "Approved",        value: counts.approved,  icon: "ti-check",   tone: "si-success", sub: counts.approved === 0 ? "None approved yet" : "Completed, now on the employee list" },
  ];
}

/** "Showing 21–40 of 53", or null when there is nothing to show. */
export function rangeLabel(page: number, pageSize: number, shown: number, matching: number): string | null {
  if (matching <= 0 || shown <= 0) return null;
  const first = (page - 1) * pageSize + 1;
  return `Showing ${first}–${first + shown - 1} of ${matching}`;
}
