// Which home screen a signed-in person lands on, kept apart from which modules they can open.
//
// Everyone except a superuser lands on the employee-style workspace (/dashboard/ess): employees, team managers and HR
// alike. HR also has a dedicated HR dashboard (/dashboard/hr), reached from the top bar and open to anyone the server
// already lets read the HR dashboard data (employees.view) and to superusers. Extra permissions add modules to the top
// bar (see navConfig.workspaceNav) and are still enforced by every route guard and API; choosing a home screen neither
// grants nor removes access. A superuser keeps the Workforce dashboard at /dashboard. A team manager's team tools are
// one click away (Team in the top bar and profile menu).

export type DashboardKey = "hr" | "manager" | "employee";

export interface DashboardSession {
  is_superuser?: boolean;
  can_manage_team?: boolean;
  permissions?: string[];
}

export function resolveDashboard(session: DashboardSession): DashboardKey {
  return session.is_superuser ? "hr" : "employee";
}

/** True when the person may open the dedicated HR dashboard: a superuser, or someone holding employees.view, the
    permission the HR dashboard's own APIs require. A team manager without it does not get it. Display only. */
export function hasHrDashboardAccess(session: DashboardSession): boolean {
  return !!session.is_superuser || (session.permissions ?? []).includes("employees.view");
}

/** True when the person may open the team dashboard (/dashboard/team). */
export function canOpenTeamDashboard(session: DashboardSession): boolean {
  return !!session.can_manage_team;
}

/** True when the person may open another employee's workspace (superusers always may). */
export function canViewEmployeeWorkspace(session: DashboardSession): boolean {
  return !!session.is_superuser || (session.permissions ?? []).includes("employees.view_workspace");
}
