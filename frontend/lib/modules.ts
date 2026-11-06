// Company modules (SaaS subscription) on the frontend: which dashboard
// routes / menu items / widgets belong to which module key. The list of
// modules comes from the `modules` claim of the access token (refreshed
// every 15 minutes) — see backend apps/accounts/tokens.py. Hiding here is
// a convenience only: the API enforces every module itself.
//
// `modules === undefined` means "unknown" (older token) → show everything,
// exactly as before this feature.

export type Modules = readonly string[] | undefined | null;

export function hasModule(modules: Modules, key: string | undefined): boolean {
  if (!key || !modules) return true;
  return modules.includes(key);
}

/** Request / approval kinds (Approvals, My Requests) → module key. */
export const KIND_MODULES: Record<string, string> = {
  leave: "leave", wfh: "wfh", expense: "expenses", attendance_correction: "attendance",
  payslip: "payroll", separation: "separation",
};

/** Dashboard route prefix → module key. Longest matching prefix wins. */
export const ROUTE_MODULES: Record<string, string> = {
  "/dashboard/attendance": "attendance",
  "/dashboard/my-attendance": "attendance",
  "/dashboard/face-id-registrations": "face_attendance",
  "/dashboard/leave": "leave",
  "/dashboard/work-from-home": "wfh",
  "/dashboard/payroll": "payroll",
  "/dashboard/my-payslip": "payroll",
  "/dashboard/expenses": "expenses",
  "/dashboard/interview-list": "recruitment",
  "/dashboard/candidate-review": "recruitment",
  "/dashboard/email-logs": "recruitment",
  "/dashboard/referrals": "recruitment",
  "/dashboard/assessments": "assessments",
  "/dashboard/separation": "separation",
  "/dashboard/announcements": "announcements",
  "/dashboard/documents": "documents",
  "/dashboard/contacts": "documents",
  "/dashboard/settings/attendance-config": "attendance",
  "/dashboard/settings/leave-policy": "leave",
  "/dashboard/settings/leave-credit-rules": "leave",
  "/dashboard/settings/holiday-calendar": "leave",
  "/dashboard/settings/payroll-config": "payroll",
  "/dashboard/settings/assets": "assets",
  "/dashboard/settings/referral-rules": "recruitment",
  "/dashboard/settings/assessment-config": "assessments",
};

export function moduleForPath(pathname: string): string | undefined {
  const match = Object.keys(ROUTE_MODULES)
    .filter(r => pathname === r || pathname.startsWith(r + "/"))
    .sort((a, b) => b.length - a.length)[0];
  return match ? ROUTE_MODULES[match] : undefined;
}

/** Module of a dashboard link (query string ignored); undefined = core. */
export function moduleForHref(href: string): string | undefined {
  return moduleForPath(href.split(/[?#]/)[0]);
}

/** `modules` claim from a JWT payload (undefined when absent). */
export function modulesFromPayload(payload: Record<string, unknown> | null | undefined): string[] | undefined {
  const m = payload?.modules;
  return Array.isArray(m) && m.every(x => typeof x === "string") ? (m as string[]) : undefined;
}
