import { describe, expect, it } from "vitest";
import type { UserInfo } from "@/lib/auth";
import { HR_HELP_PATH, HR_REQUESTS_QUEUE_PATH, supportTargetFor } from "./supportLink";

function userWith(permissions: string[], overrides: Partial<UserInfo> = {}): UserInfo {
  return { permissions, is_superuser: false, ...overrides } as UserInfo;
}

describe("supportTargetFor", () => {
  it("sends employees and managers to the HR help ticket form and offers Contact HR", () => {
    for (const user of [null, userWith([]), userWith(["leave.approve"], { can_manage_team: true })]) {
      expect(supportTargetFor(user)).toEqual({ path: HR_HELP_PATH, footerLabel: "Support", canRaiseHrHelp: true });
    }
  });

  it("sends people who answer HR tickets to the requests queue and does not offer Contact HR", () => {
    expect(supportTargetFor(userWith(["hr_help.respond"]))).toEqual({ path: HR_REQUESTS_QUEUE_PATH, footerLabel: "HR requests", canRaiseHrHelp: false });
  });

  it("treats full-access users (superuser or settings.edit) the same way", () => {
    expect(supportTargetFor(userWith([], { is_superuser: true })).path).toBe(HR_REQUESTS_QUEUE_PATH);
    expect(supportTargetFor(userWith(["settings.edit"])).canRaiseHrHelp).toBe(false);
  });
});
