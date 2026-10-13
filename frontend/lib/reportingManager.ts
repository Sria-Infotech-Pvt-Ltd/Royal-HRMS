// Manager-role employees may only have the COO, Admin Head, or HR / HR Admin /
// Branch Admin of their own branch as Reporting Manager or Reporting Approver
// (or nobody) — the backend enforces this; these helpers keep the profile form
// from offering anything else. Other roles keep the existing lists.

export const MANAGER_REPORTING_NOTE =
  "Managers can only have the COO, Admin Head, or HR / HR Admin / Branch Admin of their branch.";

export function isManagerRole(roleName: string | null | undefined, managerRoleNames: readonly string[]): boolean {
  return !!roleName && managerRoleNames.includes(roleName);
}

function managerEligibleEndpoint(base: string, branch: string | null | undefined): string {
  return branch ? `${base}?manager_approvers=1&branch=${encodeURIComponent(branch)}` : `${base}?manager_approvers=1`;
}

export function reportingManagerListEndpoint(base: string, branch: string | null | undefined, managerRole: boolean): string {
  if (managerRole) return managerEligibleEndpoint(base, branch);
  return branch ? `${base}?branch=${encodeURIComponent(branch)}` : base;
}

export function reportingApproverListEndpoint(base: string, branch: string | null | undefined, managerRole: boolean): string {
  if (managerRole) return managerEligibleEndpoint(base, branch);
  return branch ? `${base}?branch=${encodeURIComponent(branch)}` : base;
}

/**
 * True when changing the role in the form turns a non-manager into a manager
 * while the selected reporting manager isn't eligible for a Manager — that value
 * would be rejected on save, so the form clears it instead of submitting it.
 */
export function shouldClearReportingManager(args: {
  previousRole: string | null | undefined;
  nextRole: string | null | undefined;
  managerRoleNames: readonly string[];
  reportingManagerId: string | null | undefined;
  eligibleIds: readonly string[] | null | undefined;
}): boolean {
  const { previousRole, nextRole, managerRoleNames, reportingManagerId, eligibleIds } = args;
  const becameManager = isManagerRole(nextRole, managerRoleNames) && !isManagerRole(previousRole, managerRoleNames);
  return becameManager && !!reportingManagerId && !(eligibleIds ?? []).includes(reportingManagerId);
}
