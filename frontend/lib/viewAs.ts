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
export function viewWorkspacePath(employeeUuid: string): string {
  return `/dashboard/ess?as=${employeeUuid}`;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isEmployeeUuid(value: string | null | undefined): value is string {
  return !!value && UUID_PATTERN.test(value);
}
