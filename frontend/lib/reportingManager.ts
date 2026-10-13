// Manager-role employees may report only to the COO (or to nobody) — the backend
// enforces this; these helpers keep the profile form from offering anything else.

export const MANAGER_RM_NOTE = "Managers can only report to the COO.";
export const MANAGER_APPROVER_NOTE = "A Manager's Reporting Approver can be the COO, their branch HR or their Branch Admin.";

export function isManagerRole(roleName: string | null | undefined, managerRoleNames: readonly string[]): boolean {
  return !!roleName && managerRoleNames.includes(roleName);
}

export function reportingManagerListEndpoint(base: string, branch: string | null | undefined, managerRole: boolean): string {
  if (managerRole) return `${base}?coo_only=1`;
  return branch ? `${base}?branch=${encodeURIComponent(branch)}` : base;
}

/** Manager roles: the COO, branch HR and Branch Admin. Other roles: the existing list. */
export function reportingApproverListEndpoint(base: string, branch: string | null | undefined, managerRole: boolean): string {
  if (managerRole) {
    return branch ? `${base}?manager_approvers=1&branch=${encodeURIComponent(branch)}` : `${base}?manager_approvers=1`;
  }
  return branch ? `${base}?branch=${encodeURIComponent(branch)}` : base;
}

/**
 * True when changing the role in the form turns a non-manager into a manager
 * while the selected reporting manager is not a COO — that value would be
 * rejected on save, so the form clears it instead of submitting it.
 */
export function shouldClearReportingManager(args: {
  previousRole: string | null | undefined;
  nextRole: string | null | undefined;
  managerRoleNames: readonly string[];
  reportingManagerId: string | null | undefined;
  cooIds: readonly string[] | null | undefined;
}): boolean {
  const { previousRole, nextRole, managerRoleNames, reportingManagerId, cooIds } = args;
  const becameManager = isManagerRole(nextRole, managerRoleNames) && !isManagerRole(previousRole, managerRoleNames);
  return becameManager && !!reportingManagerId && !(cooIds ?? []).includes(reportingManagerId);
}
