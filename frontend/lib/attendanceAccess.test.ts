// HR attendance (/dashboard/attendance) is for attendance staff only.
// Ordinary employees can hold attendance.view / attendance.create for their
// own My Attendance page, so those alone must not open the HR screens.
// Exercises the real proxy() and buildNav(). The backend enforces the same
// rule on every API (apps/attendance/access.py) — this only hides the UI.

import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { proxy } from "@/proxy";
import { buildNav, isSection, type NavItem } from "@/lib/navConfig";

function token(payload: Record<string, unknown>): string {
  const b64 = (o: unknown) => Buffer.from(JSON.stringify(o)).toString("base64url");
  return `${b64({ alg: "none" })}.${b64({ exp: Math.floor(Date.now() / 1000) + 3600, ...payload })}.sig`;
}

function request(path: string, permissions: string[]): NextRequest {
  const headers = new Headers();
  headers.set("cookie", `royal_hrms_auth=1; royal_access_token=${token({ permissions })}`);
  return new NextRequest(new URL(path, "https://hrms.example.test"), { headers });
}

const redirectTarget = (res: Response) => {
  const loc = res.headers.get("location");
  return loc ? new URL(loc).pathname : null;
};

const EMPLOYEE = ["attendance.view", "attendance.create", "leave.view", "leave.create"];
const HR = ["attendance.view", "attendance.create", "attendance.edit", "attendance.export"];
const ADMIN = ["attendance.view", "settings.edit"];

describe("proxy: HR attendance pages", () => {
  it("sends an ordinary employee away from HR attendance, even by direct URL", () => {
    expect(redirectTarget(proxy(request("/dashboard/attendance", EMPLOYEE)))).toBe("/dashboard");
    expect(redirectTarget(proxy(request("/dashboard/attendance?employee=someone-else", EMPLOYEE)))).toBe("/dashboard");
  });

  it("keeps My Attendance open to the employee", () => {
    expect(redirectTarget(proxy(request("/dashboard/my-attendance", EMPLOYEE)))).toBeNull();
  });

  it("keeps HR and administrators' access", () => {
    expect(redirectTarget(proxy(request("/dashboard/attendance", HR)))).toBeNull();
    expect(redirectTarget(proxy(request("/dashboard/attendance", ADMIN)))).toBeNull();
  });
});

describe("navigation: Attendance (HR) item", () => {
  const items = (perms: string[]) => buildNav(perms).filter((e): e is NavItem => !isSection(e)).map(i => i.id);

  it("is hidden for an ordinary employee", () => {
    expect(items(EMPLOYEE)).not.toContain("attendance");
  });

  it("is shown to HR and administrators", () => {
    expect(items(HR)).toContain("attendance");
    expect(items(ADMIN)).toContain("attendance");
  });
});
