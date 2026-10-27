import { describe, expect, it } from "vitest";
import { canOpenTeamDashboard, resolveDashboard } from "./dashboardHome";

describe("resolveDashboard", () => {
  it("sends an ordinary employee to the workspace", () => {
    expect(resolveDashboard({ permissions: ["leave.view"] })).toBe("employee");
    expect(resolveDashboard({})).toBe("employee");
  });

  it("sends a team manager without HR access to the workspace too", () => {
    expect(resolveDashboard({ can_manage_team: true, permissions: ["leave.view"] })).toBe("employee");
  });

  it("keeps HR and superusers on the Workforce dashboard", () => {
    expect(resolveDashboard({ permissions: ["employees.view"] })).toBe("hr");
    expect(resolveDashboard({ is_superuser: true })).toBe("hr");
    expect(resolveDashboard({ can_manage_team: true, permissions: ["employees.view"] })).toBe("hr");
  });
});

describe("canOpenTeamDashboard", () => {
  it("is only for team managers", () => {
    expect(canOpenTeamDashboard({ can_manage_team: true })).toBe(true);
    expect(canOpenTeamDashboard({ permissions: ["employees.view"] })).toBe(false);
  });
});
