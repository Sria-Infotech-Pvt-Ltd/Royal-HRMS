import { describe, expect, it } from "vitest";
import { canOpenTeamDashboard, hasHrDashboardAccess, resolveDashboard } from "./dashboardHome";

const HR_PERMISSIONS = ["employees.view", "employees.edit", "recruitment.view", "leave.approve", "facial_recognition.approve"];

describe("resolveDashboard", () => {
  it("sends an ordinary employee to the workspace", () => {
    expect(resolveDashboard({ permissions: ["leave.view"] })).toBe("employee");
    expect(resolveDashboard({})).toBe("employee");
  });

  it("sends a team manager to the workspace too", () => {
    expect(resolveDashboard({ can_manage_team: true, permissions: ["leave.view", "leave.approve"] })).toBe("employee");
  });

  it("sends HR to the workspace: employees.view alone no longer picks the Workforce dashboard", () => {
    expect(resolveDashboard({ permissions: ["employees.view"] })).toBe("employee");
    expect(resolveDashboard({ permissions: HR_PERMISSIONS })).toBe("employee");
    expect(resolveDashboard({ can_manage_team: true, permissions: HR_PERMISSIONS })).toBe("employee");
  });

  it("keeps the Workforce dashboard for a superuser", () => {
    expect(resolveDashboard({ is_superuser: true })).toBe("hr");
    expect(resolveDashboard({ is_superuser: true, permissions: HR_PERMISSIONS })).toBe("hr");
  });
});

describe("canOpenTeamDashboard", () => {
  it("is only for team managers, whatever else they can do", () => {
    expect(canOpenTeamDashboard({ can_manage_team: true })).toBe(true);
    expect(canOpenTeamDashboard({ permissions: HR_PERMISSIONS })).toBe(false);
  });
});

describe("hasHrDashboardAccess", () => {
  it("is open to HR (employees.view) and to a superuser", () => {
    expect(hasHrDashboardAccess({ permissions: HR_PERMISSIONS })).toBe(true);
    expect(hasHrDashboardAccess({ is_superuser: true })).toBe(true);
  });

  it("is not open to a manager or an employee without employees.view", () => {
    expect(hasHrDashboardAccess({ can_manage_team: true, permissions: ["leave.view", "leave.approve"] })).toBe(false);
    expect(hasHrDashboardAccess({ permissions: ["leave.view"] })).toBe(false);
    expect(hasHrDashboardAccess({})).toBe(false);
  });

  it("does not decide the home screen: HR still lands on the workspace", () => {
    expect(resolveDashboard({ permissions: HR_PERMISSIONS })).toBe("employee");
  });
});
