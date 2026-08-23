import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE = "royal_hrms_auth";
const ACCESS_COOKIE = "royal_access_token";

const ROUTE_PERMISSIONS: Record<string, string | string[]> = {
  "/dashboard/announcements": "announcements.view",
  "/dashboard/interview-list": "recruitment.view",
  "/dashboard/candidate-review": "recruitment.view",
  "/dashboard/assessments": "assessments.view",
  "/dashboard/onboarding-approvals": "employees.approve",
  "/dashboard/email-logs": "recruitment.view",
  "/dashboard/employees": "employees.view",
  "/dashboard/org-chart": "org_chart.view",
  "/dashboard/branches": "settings.view",
  "/dashboard/attendance": "attendance.view",
  "/dashboard/payroll": "payroll.view",
  "/dashboard/leave": "leave.view",
  "/dashboard/expenses": "expenses.view",
  "/dashboard/approvals": ["leave.approve", "expenses.approve"],
  // /dashboard/separation intentionally absent — every employee can create
  // and view their own separation request, not just Manager/HR (same
  // self-service reasoning as my-payslip/my-attendance above). The page
  // itself scopes what each viewer sees and can do
  // (see app/dashboard/separation/_access.ts).
  "/dashboard/documents": "documents.view",
  "/dashboard/reports": "reports.view",
  "/dashboard/audit": "audit.view",
  "/dashboard/settings": "settings.view",
  "/dashboard/settings/leave-policy": "settings.view",
  "/dashboard/settings/leave-credit-rules": "settings.view",
  "/dashboard/settings/holiday-calendar": "settings.view",
};

function decodeJwtPayload(token: string): Record<string, unknown> {
  try {
    const segment = token.split(".")[1];
    if (!segment) return {};
    const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64)) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function getPermissions(request: NextRequest): string[] {
  const token = request.cookies.get(ACCESS_COOKIE)?.value;
  if (!token) return [];
  const payload = decodeJwtPayload(token);
  return Array.isArray(payload.permissions) ? (payload.permissions as string[]) : [];
}

// Onboarding/assessment/must-change-password/superuser gates used to read
// royal_hrms_user — a plain, non-httpOnly cookie the client sets via
// document.cookie (see lib/auth.ts saveAuth/setOnboardingStatus/
// setAssessmentStatus) and can therefore edit freely in devtools to force
// any value here. The real API still rejects anything that value would
// have let through, so this was never an actual data-exposure path — but
// it did mean a user could bypass these route gates and briefly see
// dashboard/change-password shell/layout they shouldn't. These now come
// from the signed royal_access_token JWT instead
// (apps.accounts.tokens.RoleBasedRefreshToken / FreshClaimsTokenRefreshSerializer
// keep the volatile ones re-derived from the current User row on every
// login/refresh), matching how getPermissions() above already worked.
function getJwtPayload(request: NextRequest): Record<string, unknown> {
  const token = request.cookies.get(ACCESS_COOKIE)?.value;
  if (!token) return {};
  return decodeJwtPayload(token);
}

function getMustChangePassword(request: NextRequest): boolean {
  return getJwtPayload(request).must_change_password === true;
}

function getOnboardingStatus(request: NextRequest): string {
  const payload = getJwtPayload(request);
  return typeof payload.onboarding_status === "string" ? payload.onboarding_status : "complete";
}

function getAssessmentStatus(request: NextRequest): string {
  const payload = getJwtPayload(request);
  return typeof payload.assessment_status === "string" ? payload.assessment_status : "complete";
}

function getCanManageTeam(request: NextRequest): boolean {
  return getJwtPayload(request).can_manage_team === true;
}

function getCanManageBranch(request: NextRequest): boolean {
  return getJwtPayload(request).can_manage_branch === true;
}

function getIsSuperuser(request: NextRequest): boolean {
  return getJwtPayload(request).is_superuser === true;
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // API routes — attach the access token as an Authorization header so the
  // Django backend can authenticate all HTTP methods (GET, POST, PUT, PATCH, DELETE).
  // The rewrite in next.config.ts handles forwarding to the backend.
  if (pathname.startsWith("/api/")) {
    const token = request.cookies.get(ACCESS_COOKIE)?.value;
    if (token) {
      const headers = new Headers(request.headers);
      headers.set("Authorization", `Bearer ${token}`);
      return NextResponse.next({ request: { headers } });
    }
    return NextResponse.next();
  }

  // Platform-admin area — a completely separate auth domain from every
  // tenant login (see backend apps/tenants/authentication.py). Checked
  // against its own cookie (platform_access_token, httpOnly — readable
  // here because proxy.ts runs server-side, unlike client JS) rather than
  // the tenant AUTH_COOKIE/ACCESS_COOKIE above, and returns early so none
  // of the tenant-specific onboarding/permission logic below ever applies
  // to it.
  if (pathname.startsWith("/platform-admin")) {
    const isPlatformLoginPage = pathname === "/platform-admin/login";
    // Forgot-password is reachable by definition without a valid session —
    // same unauthenticated-entry-point treatment as the login page itself.
    const isPlatformForgotPasswordPage = pathname.startsWith("/platform-admin/forgot-password");
    const platformToken = request.cookies.get("platform_access_token")?.value;
    const isPlatformTokenValid = (() => {
      if (!platformToken) return false;
      try {
        const payload = decodeJwtPayload(platformToken);
        const exp = payload.exp as number | undefined;
        return exp ? exp * 1000 > Date.now() : true;
      } catch { return false; }
    })();

    if (!isPlatformTokenValid && !isPlatformLoginPage && !isPlatformForgotPasswordPage) {
      return NextResponse.redirect(new URL("/platform-admin/login", request.url));
    }
    if (isPlatformTokenValid && (isPlatformLoginPage || isPlatformForgotPasswordPage)) {
      return NextResponse.redirect(new URL("/platform-admin", request.url));
    }
    return NextResponse.next();
  }

  const isAuthenticated = request.cookies.get(AUTH_COOKIE)?.value === "1";
  const isLoginPage = pathname.startsWith("/login");
  const isOnboarding = pathname.startsWith("/onboarding");
  const isChangePasswordPage = pathname.startsWith("/change-password");

  if (!isAuthenticated && !isLoginPage) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (isAuthenticated && isLoginPage) {
    const token = request.cookies.get(ACCESS_COOKIE)?.value;
    const isTokenValid = (() => {
      if (!token) return false;
      try {
        const payload = decodeJwtPayload(token);
        const exp = payload.exp as number | undefined;
        return exp ? exp * 1000 > Date.now() : true;
      } catch { return false; }
    })();
    if (isTokenValid) {
      const dest = getMustChangePassword(request) ? "/change-password" : "/dashboard";
      return NextResponse.redirect(new URL(dest, request.url));
    }
  }

  // A temporary or admin-reset password must be replaced before anything
  // else is reachable — checked ahead of onboarding/assessment/permission
  // gates below since fixing the account's credentials comes first.
  if (isAuthenticated && !isLoginPage) {
    const mustChangePassword = getMustChangePassword(request);
    if (mustChangePassword && !isChangePasswordPage) {
      return NextResponse.redirect(new URL("/change-password", request.url));
    }
    if (!mustChangePassword && isChangePasswordPage) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
  }

  if (isAuthenticated && !isChangePasswordPage) {
    const onboardingStatus = getOnboardingStatus(request);
    const assessmentStatus = getAssessmentStatus(request);
    const canManageTeam    = getCanManageTeam(request);
    const canManageBranch  = getCanManageBranch(request);
    const isSuperuser      = getIsSuperuser(request);
    const isAssessmentsPage = pathname.startsWith("/onboarding/assessments");

    // "approved" means HR has approved the onboarding form; only then can
    // the employee access the assessment portal.
    // Superusers are platform/IT-provisioned admin accounts, never hired
    // through the candidate pipeline — the onboarding wizard never applies
    // to them, regardless of their onboarding_status value (see login/page.tsx
    // for the matching exemption at login time). Branch Admin is the same
    // kind of administrative account (assigned at branch-creation time, not
    // hired through the candidate pipeline), so it gets the same exemption.
    const needsOnboarding = onboardingStatus !== "complete" && !isSuperuser && !canManageBranch;
    // Default assessments get auto-assigned to every new employee record on
    // creation — including managers — with no role distinction, so a manager
    // can end up with assessment_status "pending" despite the pre-onboarding
    // assessment portal being meant for new-hire employees, not managers.
    // Exempt can_manage_team here since the backend doesn't. Superusers and
    // Branch Admin are exempt too, for the same reason as needsOnboarding above.
    const needsAssessments = onboardingStatus === "complete" && assessmentStatus === "pending" && !canManageTeam && !canManageBranch && !isSuperuser;

    // Block /onboarding/assessments until HR has approved the onboarding form.
    // Without this explicit check the route slips through because isOnboarding
    // is true for any /onboarding/* path, masking the needsOnboarding guard below.
    if (isAssessmentsPage && needsOnboarding) {
      return NextResponse.redirect(new URL("/onboarding", request.url));
    }

    // Onboarding-incomplete users must stay on /onboarding
    if (needsOnboarding && !isOnboarding) {
      return NextResponse.redirect(new URL("/onboarding", request.url));
    }

    // Employees with a pending assessment must go to /onboarding/assessments
    if (needsAssessments && !isAssessmentsPage) {
      return NextResponse.redirect(new URL("/onboarding/assessments", request.url));
    }

    // Fully onboarded or approved users must not linger on /onboarding base page
    if (!needsOnboarding && isOnboarding && !needsAssessments && !isAssessmentsPage) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
  }

  // Permission check for protected dashboard routes
  if (isAuthenticated && pathname.startsWith("/dashboard")) {
    const matchedRoute = Object.keys(ROUTE_PERMISSIONS)
      .filter(r => pathname === r || pathname.startsWith(r + "/"))
      .sort((a, b) => b.length - a.length)[0];

    if (matchedRoute) {
      const needed = ROUTE_PERMISSIONS[matchedRoute];
      const permissions = getPermissions(request);
      const hasPermission = Array.isArray(needed)
        ? needed.some(p => permissions.includes(p))
        : permissions.includes(needed);
      if (!hasPermission) {
        return NextResponse.redirect(new URL("/dashboard", request.url));
      }
    }
  }

  return NextResponse.next();
}

export const config = {
  // "models/" is excluded so face-api.js can load its weight files (JSON
  // manifests + extensionless shard binaries) under /public/models/ even
  // when the current user still needs onboarding — otherwise this proxy's
  // onboarding-gate redirect (below) intercepts those static asset requests
  // and 307s them to /onboarding, and face-api.js silently fails trying to
  // parse the returned HTML as model weights.
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico|models/|.*\\.(?:png|jpg|jpeg|svg|gif|webp|ico|woff2?|ttf|otf|mp4|pdf|json)$).*)"],
};
