// Which dashboard pages get the shared Back button (rendered by DashboardShell), and where Back goes when there is no history.

const HOME = "/dashboard";

/** The landing pages people start from: nowhere to go back to. The employee directory is a fixed-height page and is a top-level destination too. */
const NO_BACK_EXACT = new Set([HOME, "/dashboard/ess", "/dashboard/hr", "/dashboard/team", "/dashboard/employees"]);

/** Pages that already draw their own Back (a header button, or "Back to ..." inside a detail page): the shared one would double it. */
const OWN_BACK_PREFIXES = [
  "/dashboard/org-chart",
  "/dashboard/announcements",
  "/dashboard/assessments",
  "/dashboard/candidate-review",
  "/dashboard/face-id-registrations",
  "/dashboard/performance",
  "/dashboard/privacy",
  "/dashboard/security",
  "/dashboard/settings/access",
  "/dashboard/settings/approval-rules",
  "/dashboard/settings/assessment-config",
  "/dashboard/settings/attendance-config",
  "/dashboard/settings/audit",
  "/dashboard/settings/company",
  "/dashboard/settings/email-templates",
  "/dashboard/settings/employee-code",
  "/dashboard/settings/holiday-calendar",
  "/dashboard/settings/leave-policy",
  "/dashboard/settings/notifications",
  "/dashboard/settings/onboarding-fields",
  "/dashboard/settings/payroll-config",
  "/dashboard/settings/project-sync",
  "/dashboard/settings/referral-rules",
  "/dashboard/settings/smtp",
  "/dashboard/payroll/",
  "/dashboard/separation/",
  "/dashboard/employees/",
  "/dashboard/hire/",
];

function trimTrailingSlash(pathname: string): string {
  return pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
}

export function shouldShowBackButton(pathname: string): boolean {
  const path = trimTrailingSlash(pathname);
  if (!path.startsWith(HOME) || NO_BACK_EXACT.has(path)) return false;
  // A prefix ending in "/" covers only the pages below it (the list page itself has no Back); one without covers the page and everything below.
  const hasOwnBack = OWN_BACK_PREFIXES.some(prefix => prefix.endsWith("/") ? path.startsWith(prefix) : path === prefix || path.startsWith(`${prefix}/`));
  return !hasOwnBack;
}

/** Where Back goes when the page was opened directly (no earlier page to return to): the page above this one, else the dashboard. */
export function backFallbackPath(pathname: string): string {
  const path = trimTrailingSlash(pathname);
  const parent = path.slice(0, path.lastIndexOf("/"));
  return parent.startsWith(HOME) && parent.length > HOME.length ? parent : HOME;
}
