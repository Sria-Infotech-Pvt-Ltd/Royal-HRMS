// Announcements are self-service: any signed-in employee can open the page
// (the backend shows each user only the posts meant for them), while other
// permission-protected routes stay protected. Exercises the real proxy() and
// buildNav(), not copies of their rules.

import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { proxy } from "@/proxy";
import { buildNav, isSection, type NavItem } from "@/lib/navConfig";

// Unsigned test token: proxy() only base64-decodes the payload for routing
// decisions; real authorization is the backend's (it verifies the signature).
function token(payload: Record<string, unknown>): string {
  const b64 = (o: unknown) => Buffer.from(JSON.stringify(o)).toString("base64url");
  return `${b64({ alg: "none" })}.${b64({ exp: Math.floor(Date.now() / 1000) + 3600, ...payload })}.sig`;
}

function request(path: string, opts: { signedIn: boolean; permissions?: string[] }): NextRequest {
  const headers = new Headers();
  if (opts.signedIn) {
    headers.set("cookie", `royal_hrms_auth=1; royal_access_token=${token({ permissions: opts.permissions ?? [] })}`);
  }
  return new NextRequest(new URL(path, "https://hrms.example.test"), { headers });
}

function redirectTarget(res: Response): string | null {
  const loc = res.headers.get("location");
  return loc ? new URL(loc).pathname : null;
}

const EMPLOYEE_PERMS = ["payroll.view_own", "leave.apply"];        // no announcements.view

describe("proxy: /dashboard/announcements", () => {
  it("lets a signed-in employee without announcements.view open the page (View All / direct URL)", () => {
    expect(redirectTarget(proxy(request("/dashboard/announcements", { signedIn: true, permissions: EMPLOYEE_PERMS })))).toBeNull();
  });

  it("still requires sign-in", () => {
    expect(redirectTarget(proxy(request("/dashboard/announcements", { signedIn: false })))).toBe("/login");
  });

  it("keeps other permission-protected routes protected", () => {
    expect(redirectTarget(proxy(request("/dashboard/payroll", { signedIn: true, permissions: EMPLOYEE_PERMS })))).toBe("/dashboard");
    expect(redirectTarget(proxy(request("/dashboard/employees", { signedIn: true, permissions: EMPLOYEE_PERMS })))).toBe("/dashboard");
    expect(redirectTarget(proxy(request("/dashboard/payroll", { signedIn: true, permissions: ["payroll.view"] })))).toBeNull();
  });
});

describe("navigation: Announcements item", () => {
  const items = (perms: string[]) =>
    buildNav(perms).filter((e): e is NavItem => !isSection(e)).map(i => i.id);

  it("is shown to an employee without announcements.view", () => {
    expect(items(EMPLOYEE_PERMS)).toContain("announcements");
  });

  it("does not open up permission-gated items", () => {
    expect(items(EMPLOYEE_PERMS)).not.toContain("payroll");
    expect(items(EMPLOYEE_PERMS)).not.toContain("employees");
  });
});
