export interface NavSection {
  section: string;
  /** Where the section's pages live: a dropdown on the top bar (default) or the profile menu. */
  placement?: "bar" | "profile";
}
export interface NavItem {
  id: string;
  icon: string;
  label: string;
  badge?: string;
  path: string;
  permission: string | string[] | null; // null = always visible; string[] = any one grants access
  comingSoon?: boolean;       // true = non-clickable, shows "Soon" badge
  /** Shorter label for the flat top-nav strip, where the sidebar's fuller label doesn't fit — falls back to `label` when unset. */
  topNavLabel?: string;
  /** Renders as a direct link on the top bar instead of inside its section's dropdown. */
  pinned?: boolean;
}
export type NavEntry = NavSection | NavItem;

export function isSection(e: NavEntry): e is NavSection {
  return "section" in e;
}

const ALL_NAV: NavEntry[] = [
  { section: "Main" },
  { id: "dashboard", icon: "ti-layout-dashboard", label: "Dashboard", path: "/dashboard", permission: null, pinned: true },
  { id: "announcements", icon: "ti-speakerphone", label: "Announcements", path: "/dashboard/announcements", permission: "announcements.view", pinned: true },

  { section: "Recruitment" },
  { id: "interview-list", icon: "ti-users", label: "Interview List", path: "/dashboard/interview-list", permission: "recruitment.view" },
  { id: "candidate-review", icon: "ti-user-check", label: "Review & Onboarding", path: "/dashboard/candidate-review", permission: "recruitment.view" },
  { id: "assessments", icon: "ti-clipboard-check", label: "Assessments", path: "/dashboard/assessments", permission: "assessments.view" },
  { id: "face-id-registrations", icon: "ti-face-id", label: "Face ID Registrations", path: "/dashboard/face-id-registrations", permission: "facial_recognition.approve" },

  { section: "Workforce" },
  { id: "employees", icon: "ti-id-badge", label: "Employees", path: "/dashboard/employees", permission: "employees.view" },
  { id: "org-chart", icon: "ti-sitemap", label: "Organization Management", path: "/dashboard/org-chart", permission: "org_chart.view", topNavLabel: "Organization" },
  // Performance nav item removed for now (admin-side review-cycle management
  // page) — the ESS "Growth"/"Appraisals" self-service tabs still use the
  // same apps.performance backend and are unaffected; only this top-level
  // admin entry point is hidden.
  // Reporting Managers only (performance.review_team): the appraisal review workspace.
  // HR's cycle-management view stays reachable by URL but is deliberately not in the nav.
  { id: "performance", icon: "ti-star", label: "Performance", path: "/dashboard/performance", permission: "performance.review_team" },
  { id: "branches", icon: "ti-building-skyscraper", label: "Company Codes", path: "/dashboard/branches", permission: "branches.view" },

  { section: "Time & Pay" },
  { id: "attendance", icon: "ti-clock", label: "Attendance", path: "/dashboard/attendance", permission: "attendance.create" },
  { id: "payroll", icon: "ti-report-money", label: "Payroll", path: "/dashboard/payroll", permission: "payroll.view" },
  { id: "leave", icon: "ti-beach", label: "Leave Management", path: "/dashboard/leave", permission: "leave.view", topNavLabel: "Leave" },
  { id: "work-from-home", icon: "ti-home-2", label: "Work From Home", path: "/dashboard/work-from-home", permission: "wfh.view" },
  { id: "expenses", icon: "ti-wallet", label: "Expenses", path: "/dashboard/expenses", permission: "expenses.view" },

  { section: "HR Ops" },
  { id: "approvals", icon: "ti-checks", label: "Approvals", path: "/dashboard/approvals", permission: ["leave.approve", "expenses.approve", "payroll.edit", "employees.approve", "employees.raise_action", "facial_recognition.approve"] },
  // permission: null — every employee can create/view their own request here,
  // not just Manager/HR; the page itself scopes what each viewer sees.
  { id: "separation", icon: "ti-logout", label: "Separation & Exit", path: "/dashboard/separation", permission: null },
  { id: "documents", icon: "ti-folder", label: "Document Center", path: "/dashboard/documents", permission: "documents.view" },

  { section: "My", placement: "profile" },
  // My Workspace is the single navigation entry for self-service modules
  // that also have legacy standalone routes. Those routes remain available
  // for bookmarks and deep links; distinct modules stay in the nav below.
  { id: "ess", icon: "ti-apps", label: "My Workspace", path: "/dashboard/ess", permission: null },
  // Self-service pages that had no link anywhere in the navigation; reachable from the profile menu.
  { id: "my-attendance", icon: "ti-clock", label: "My Attendance", path: "/dashboard/my-attendance", permission: null },
  { id: "my-requests", icon: "ti-checklist", label: "My Requests", path: "/dashboard/my-requests", permission: null },
  { id: "my-payslips", icon: "ti-receipt-2", label: "My Payslips", path: "/dashboard/my-payslip", permission: null },
  // My Assessments is the employee entry point to the shared assessments page;
  // it is not a tab in My Workspace.
  // Same path as the admin "Assessments" entry above (Recruitment section) —
  // the page itself picks admin management vs. EmployeeMyAssessments based on
  // permission (see app/dashboard/assessments/page.tsx's isAdminView check),
  // but without this separate entry an employee with no assessments.* grant
  // (i.e. everyone assigned an onboarding assessment) had no sidebar link.
  { id: "my-assessments", icon: "ti-clipboard-check", label: "My Assessments", path: "/dashboard/assessments", permission: null },
  { id: "referrals", icon: "ti-user-plus", label: "My Referrals", path: "/dashboard/referrals", permission: null },
  // Interviewers see only the interviews assigned to them; the page is empty for everyone else.
  { id: "my-interviews", icon: "ti-message-2-star", label: "My Interviews", path: "/dashboard/my-interviews", permission: null },

  { section: "System" },
  { id: "reports", icon: "ti-chart-bar", label: "Reports", path: "/dashboard/reports", permission: ["reports.view", "employees.export", "attendance.view", "leave.approve", "wfh.approve", "separation.approve", "facial_recognition.approve", "recruitment.view"] },
  { id: "audit", icon: "ti-shield-check", label: "Audit Log", path: "/dashboard/settings/audit", permission: "audit.view" },
  { id: "email-logs", icon: "ti-mail", label: "Email Logs", path: "/dashboard/email-logs", permission: "email_logs.view" },
  { id: "settings", icon: "ti-settings", label: "Settings", path: "/dashboard/settings", permission: "settings.view" },
];

export function buildNav(permissions: string[]): NavEntry[] {
  const permSet = new Set(permissions);
  const result: NavEntry[] = [];
  let pendingSection: NavEntry | null = null;
  let sectionHasItem = false;

  for (const entry of ALL_NAV) {
    if (isSection(entry)) {
      pendingSection = entry;
      sectionHasItem = false;
    } else {
      const item = entry as NavItem;
      const permVisible = item.permission === null
        || (Array.isArray(item.permission)
          ? item.permission.some(p => permSet.has(p))
          : permSet.has(item.permission));
      if (permVisible) {
        if (pendingSection && !sectionHasItem) result.push(pendingSection);
        result.push(item);
        sectionHasItem = true;
      }
    }
  }
  return result;
}

/** One entry on the top bar: a direct link, or a dropdown holding a section's pages. */
export type BarEntry =
  | { kind: "link"; item: NavItem }
  | { kind: "menu"; id: string; title: string; items: NavItem[] };

export interface NavGroups {
  bar: BarEntry[];
  /** The pages shown in the profile menu. */
  profile: NavItem[];
}

/**
 * Groups the permission-filtered nav (buildNav's output) for the top bar. A section with no visible pages
 * disappears, a section with exactly one becomes a plain link, and "profile" sections go to the profile menu.
 */
export function groupNav(entries: NavEntry[]): NavGroups {
  const sections: { section: NavSection; items: NavItem[] }[] = [];
  for (const entry of entries) {
    if (isSection(entry)) sections.push({ section: entry, items: [] });
    else sections[sections.length - 1]?.items.push(entry);
  }

  const groups: NavGroups = { bar: [], profile: [] };
  for (const { section, items } of sections) {
    if (section.placement === "profile") {
      groups.profile.push(...items);
      continue;
    }
    const inMenu = items.filter(item => !item.pinned);
    items.filter(item => item.pinned).forEach(item => groups.bar.push({ kind: "link", item }));
    if (inMenu.length === 1) groups.bar.push({ kind: "link", item: inMenu[0] });
    else if (inMenu.length > 1) groups.bar.push({ kind: "menu", id: section.section.toLowerCase().replace(/\W+/g, "-"), title: section.section, items: inMenu });
  }
  return groups;
}

/**
 * Pages open to every employee (no permission needed, or a baseline one): Leave, Expenses, Documents, Reports, ... The workspace
 * (/dashboard/ess) has its own tab bar, so these never appear in the top bar there; only the modules a person's
 * extra permissions add do.
 */
export const SELF_SERVICE_NAV_IDS: ReadonlySet<string> = new Set([
  "dashboard", "leave", "work-from-home", "expenses", "documents", "org-chart", "separation",
]);

/**
 * The team manager's own dashboard, linked from the top bar and the profile menu. It reads "Dashboard" for a manager (it
 * replaces the generic Dashboard link); a superuser, who also has the Workforce "Dashboard", sees "Manager Dashboard".
 */
export const TEAM_DASHBOARD_NAV_ITEM: NavItem = {
  id: "team-dashboard", icon: "ti-layout-dashboard", label: "Dashboard", path: "/dashboard/team", permission: null, pinned: true,
};

/**
 * The top bar for the employee-style workspace: only the modules this person's permissions add on top of
 * self-service. An ordinary employee gets an empty bar (their navigation is unchanged); HR and managers get
 * Employees, Recruitment, Approvals and so on, only where they hold the permission. This changes what is shown, never
 * what is allowed: every route and API still enforces its own permission.
 */
export function workspaceNav(permissions: string[]): NavGroups {
  return groupNav(buildNav(permissions).filter(entry => isSection(entry) || !SELF_SERVICE_NAV_IDS.has(entry.id)));
}

/**
 * For a team manager: the Manager Dashboard link goes after any HR Dashboard link. The generic "Dashboard" link is
 * dropped, because for a non-superuser it only led to the workspace (My Workspace is in the profile menu and the
 * dashboard banner). A superuser's Dashboard is the Workforce dashboard, so `keepDashboard` leaves it in place.
 */
export function withTeamLink(bar: BarEntry[], isTeamManager: boolean, options: { keepDashboard?: boolean } = {}): BarEntry[] {
  if (!isTeamManager) return bar;
  const rest = options.keepDashboard ? bar : bar.filter(candidate => !(candidate.kind === "link" && candidate.item.id === "dashboard"));
  // Next to another dashboard (the superuser's, or HR's) it needs its full name to be told apart.
  const hasOtherDashboard = options.keepDashboard || rest.some(candidate => candidate.kind === "link" && candidate.item.id === "hr-dashboard");
  const item = hasOtherDashboard ? { ...TEAM_DASHBOARD_NAV_ITEM, label: "Manager Dashboard" } : TEAM_DASHBOARD_NAV_ITEM;
  const entry: BarEntry = { kind: "link", item };
  const lastHomeAt = rest.reduce((last, candidate, index) => (candidate.kind === "link" && HOME_NAV_IDS.has(candidate.item.id) ? index : last), -1);
  return [...rest.slice(0, lastHomeAt + 1), entry, ...rest.slice(lastHomeAt + 1)];
}

const HOME_NAV_IDS: ReadonlySet<string> = new Set(["dashboard", "hr-dashboard"]);

/** HR's own dashboard. Shown to people the HR dashboard's APIs already authorize (see dashboardHome.hasHrDashboardAccess). */
export const HR_DASHBOARD_NAV_ITEM: NavItem = {
  id: "hr-dashboard", icon: "ti-layout-dashboard", label: "HR Dashboard", path: "/dashboard/hr", permission: "employees.view", pinned: true,
};

/**
 * For an HR user (not a superuser, whose Dashboard already is the Workforce dashboard): "HR Dashboard" leads the bar,
 * replacing the single Dashboard link, which for HR only led to the workspace. My Workspace is reached from the HR
 * dashboard's banner button and the profile menu, not the bar. Everyone else's bar is returned untouched.
 * Presentation only: the routes still enforce their own permissions.
 */
export function withHomeLinks(bar: BarEntry[], options: { hasHrDashboard: boolean; isSuperuser: boolean }): BarEntry[] {
  if (!options.hasHrDashboard || options.isSuperuser) return bar;
  const rest = bar.filter(entry => !(entry.kind === "link" && entry.item.id === "dashboard"));
  return [{ kind: "link", item: HR_DASHBOARD_NAV_ITEM }, ...rest];
}

/**
 * Profile-menu links whose destination is already a tab of the employee-style workspace (Attendance, Requests,
 * Payslips). "My Workspace" itself stays as a shortcut; Assessments, Referrals and Interviews are NOT workspace tabs,
 * so their links stay too.
 */
export const WORKSPACE_DUPLICATE_NAV_IDS: ReadonlySet<string> = new Set(["my-attendance", "my-requests", "my-payslips"]);

/**
 * The links in the profile dropdown. A person whose home screen is the workspace does not get links that only repeat
 * its tabs; a superuser, whose home is the Workforce dashboard, keeps them (it is their way into the workspace).
 * Team Dashboard is added first for a team manager. This is presentation only: the pages, route guards and APIs are
 * unchanged.
 */
export function profileMenuItems(items: NavItem[], options: { homeIsWorkspace: boolean; isTeamManager: boolean; hasHrDashboard?: boolean }): NavItem[] {
  const kept = options.homeIsWorkspace ? items.filter(item => !WORKSPACE_DUPLICATE_NAV_IDS.has(item.id)) : items;
  const teamItem = options.homeIsWorkspace && !options.hasHrDashboard ? TEAM_DASHBOARD_NAV_ITEM : { ...TEAM_DASHBOARD_NAV_ITEM, label: "Manager Dashboard" };
  return options.isTeamManager ? [teamItem, ...kept] : kept;
}
