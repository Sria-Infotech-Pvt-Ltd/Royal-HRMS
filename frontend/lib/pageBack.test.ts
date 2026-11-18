import { describe, expect, it } from "vitest";
import { backFallbackPath, shouldShowBackButton } from "./pageBack";

describe("shouldShowBackButton", () => {
  it("shows on ordinary pages reached from the menu", () => {
    for (const path of ["/dashboard/branches", "/dashboard/leave", "/dashboard/expenses", "/dashboard/payroll", "/dashboard/separation", "/dashboard/settings", "/dashboard/reports/attendance"]) {
      expect(shouldShowBackButton(path), path).toBe(true);
    }
  });

  it("stays off the landing pages", () => {
    for (const path of ["/dashboard", "/dashboard/", "/dashboard/ess", "/dashboard/hr", "/dashboard/team", "/dashboard/employees"]) {
      expect(shouldShowBackButton(path), path).toBe(false);
    }
  });

  it("stays off pages that already have their own Back, so it is never doubled", () => {
    for (const path of ["/dashboard/org-chart", "/dashboard/announcements", "/dashboard/assessments", "/dashboard/performance", "/dashboard/payroll/runs/12", "/dashboard/separation/abc", "/dashboard/employees/E001/onboarding", "/dashboard/settings/access", "/dashboard/settings/audit", "/dashboard/hire/xyz"]) {
      expect(shouldShowBackButton(path), path).toBe(false);
    }
  });

  it("is off on every Settings sub-page that draws its own Back, but on for the Settings home and Leave credit rules", () => {
    for (const path of ["/dashboard/settings/audit", "/dashboard/settings/smtp", "/dashboard/settings/company", "/dashboard/settings/leave-policy"]) {
      expect(shouldShowBackButton(path), path).toBe(false);
    }
    for (const path of ["/dashboard/settings", "/dashboard/settings/leave-credit-rules"]) {
      expect(shouldShowBackButton(path), path).toBe(true);
    }
  });

  it("is off outside the dashboard", () => {
    expect(shouldShowBackButton("/login")).toBe(false);
  });
});

describe("backFallbackPath", () => {
  it("goes up one level, never above the dashboard", () => {
    expect(backFallbackPath("/dashboard/reports/attendance")).toBe("/dashboard/reports");
    expect(backFallbackPath("/dashboard/branches")).toBe("/dashboard");
    expect(backFallbackPath("/dashboard/branches/")).toBe("/dashboard");
  });
});
