import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE   = "royal_hrms_auth";
const ACCESS_COOKIE = "royal_access_token";
const USER_COOKIE   = "royal_hrms_user";

const ROUTE_PERMISSIONS: Record<string, string> = {
  "/dashboard/announcements":    "announcements.view",
  "/dashboard/interview-list":   "recruitment.view",
  "/dashboard/candidate-review":        "recruitment.view",
  "/dashboard/assessments":            "assessments.view",
  "/dashboard/onboarding-approvals":   "employees.approve",
  "/dashboard/email-logs":             "recruitment.view",
  "/dashboard/employees":        "employees.view",
  "/dashboard/org-chart":        "employees.view",
  "/dashboard/branches":         "settings.view",
  "/dashboard/attendance":       "attendance.view",
  "/dashboard/payroll":          "payroll.view",
  "/dashboard/my-payslip":       "payroll.view",
  "/dashboard/leave":            "leave.view",
  "/dashboard/expenses":         "expenses.view",
  "/dashboard/approvals":        "leave.view",
  "/dashboard/separation":       "employees.view",
  "/dashboard/documents":        "documents.view",
  "/dashboard/reports":          "reports.view",
  "/dashboard/audit":            "audit.view",
  "/dashboard/settings":                      "settings.view",
  "/dashboard/settings/leave-policy":        "settings.view",
  "/dashboard/settings/leave-credit-rules":  "settings.view",
  "/dashboard/settings/holiday-calendar":    "settings.view",
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
  if (token) {
    const payload = decodeJwtPayload(token);
    if (Array.isArray(payload.permissions)) {
      return payload.permissions as string[];
    }
  }
  const raw = request.cookies.get(USER_COOKIE)?.value;
  if (!raw) return [];
  try {
    const user = JSON.parse(decodeURIComponent(raw)) as { permissions?: unknown };
    return Array.isArray(user.permissions) ? (user.permissions as string[]) : [];
  } catch {
    return [];
  }
}

function getOnboardingStatus(request: NextRequest): string {
  const raw = request.cookies.get(USER_COOKIE)?.value;
  if (!raw) return "complete"; // unknown — allow through, dashboard will handle
  try {
    const user = JSON.parse(decodeURIComponent(raw)) as { onboarding_status?: string };
    return user.onboarding_status ?? "complete";
  } catch {
    return "complete";
  }
}

function getAssessmentStatus(request: NextRequest): string {
  const raw = request.cookies.get(USER_COOKIE)?.value;
  if (!raw) return "complete";
  try {
    const user = JSON.parse(decodeURIComponent(raw)) as { assessment_status?: string };
    return user.assessment_status ?? "complete";
  } catch {
    return "complete";
  }
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

  const isAuthenticated = request.cookies.get(AUTH_COOKIE)?.value === "1";
  const isLoginPage     = pathname.startsWith("/login");
  const isOnboarding    = pathname.startsWith("/onboarding");

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
    if (isTokenValid) return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  if (isAuthenticated) {
    const onboardingStatus  = getOnboardingStatus(request);
    const assessmentStatus  = getAssessmentStatus(request);
    const isAssessmentsPage = pathname.startsWith("/onboarding/assessments");

    // "approved" means HR has approved the onboarding form; only then can
    // the employee access the assessment portal.
    const needsOnboarding  = onboardingStatus !== "complete" && onboardingStatus !== "approved";
    const needsAssessments = onboardingStatus === "approved" && assessmentStatus === "pending";

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
      const needed      = ROUTE_PERMISSIONS[matchedRoute];
      const permissions = getPermissions(request);
      if (!permissions.includes(needed)) {
        return NextResponse.redirect(new URL("/dashboard", request.url));
      }
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico|.*\\.(?:png|jpg|jpeg|svg|gif|webp|ico|woff2?|ttf|otf|mp4|pdf)$).*)"],
};
