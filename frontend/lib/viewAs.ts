// "View as employee": while an admin looks at an employee's workspace, every API call of that page carries the
// employee's id so the server answers with that employee's own data. The server only honours it for people who
// hold employees.view_workspace, and only for reads.

export const VIEW_AS_HEADER = "X-View-As-Employee";

let viewedEmployeeUuid: string | null = null;

export function setViewAsEmployee(uuid: string | null): void {
  viewedEmployeeUuid = uuid;
}

export function getViewAsEmployee(): string | null {
  return viewedEmployeeUuid;
}

// Calls that always belong to the person signed in, even while viewing someone else.
const OWN_IDENTITY_PATHS = ["/notifications/", "/login/", "/logout/", "/token/refresh/"];

/** The header to attach to a request for `url`, or null when it should not carry one. */
export function viewAsHeaderFor(url: string | undefined): { name: string; value: string } | null {
  if (!viewedEmployeeUuid) return null;
  if (url && OWN_IDENTITY_PATHS.some(path => url.startsWith(path))) return null;
  return { name: VIEW_AS_HEADER, value: viewedEmployeeUuid };
}

/** The workspace page for an employee, read-only. */
export function viewWorkspacePath(employee: string): string {
  return `/dashboard/ess?as=${encodeURIComponent(employee)}`;
}

/** The admin profile page of an employee (tabs, salary, actions) — bypasses the redirect to their workspace. */
export function adminProfilePath(employeeCode: string): string {
  return `/dashboard/employees/${encodeURIComponent(employeeCode)}?view=profile`;
}

// An employee's id (uuid) or their employee code (EMP00081, UAT26-050, ...): what the profile page address carries.
const VIEW_AS_TARGET_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{1,39}$/;

export function isViewAsTarget(value: string | null | undefined): value is string {
  return !!value && VIEW_AS_TARGET_PATTERN.test(value);
}
