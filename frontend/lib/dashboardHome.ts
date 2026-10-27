// Which home screen a signed-in person lands on. Everyone who is not HR/admin gets the workspace
// (/dashboard/ess), including team managers; their team tools live on /dashboard/team, reached from the
// profile menu.

export type DashboardKey = "hr" | "manager" | "employee";

export interface DashboardSession {
  is_superuser?: boolean;
  can_manage_team?: boolean;
  permissions?: string[];
}

export function hasHrAccess(session: DashboardSession): boolean {
  return !!session.is_superuser || (session.permissions ?? []).includes("employees.view");
}

export function resolveDashboard(session: DashboardSession): DashboardKey {
  if (hasHrAccess(session)) return "hr";
  return "employee";
}

/** True when the person may open the team dashboard (/dashboard/team). */
export function canOpenTeamDashboard(session: DashboardSession): boolean {
  return !!session.can_manage_team;
}

/** True when the person may open another employee's workspace (superusers always may). */
export function canViewEmployeeWorkspace(session: DashboardSession): boolean {
  return !!session.is_superuser || (session.permissions ?? []).includes("employees.view_workspace");
}
