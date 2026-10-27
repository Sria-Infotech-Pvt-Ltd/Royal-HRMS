import { describe, expect, it } from "vitest";
import {
  isManagerRole, reportingApproverListEndpoint, reportingManagerListEndpoint, shouldClearReportingManager,
} from "./reportingManager";

const MANAGER_ROLES = ["manager", "manager__team_lead"];
const BASE = "/employees/managers/";

describe("isManagerRole", () => {
  it("recognises manager roles from the roles list", () => {
    expect(isManagerRole("manager", MANAGER_ROLES)).toBe(true);
    expect(isManagerRole("employee", MANAGER_ROLES)).toBe(false);
    expect(isManagerRole("", MANAGER_ROLES)).toBe(false);
    expect(isManagerRole(undefined, MANAGER_ROLES)).toBe(false);
  });
});

describe("reportingManagerListEndpoint", () => {
  it("offers the Manager-eligible list (COO, Admin Head, branch HR / HR Admin / Branch Admin)", () => {
    expect(reportingManagerListEndpoint(BASE, "Hyderabad", true)).toBe(`${BASE}?manager_approvers=1&branch=Hyderabad`);
  });

  it("keeps the existing branch-filtered list for other roles", () => {
    expect(reportingManagerListEndpoint(BASE, "Mumbai HQ", false)).toBe(`${BASE}?branch=Mumbai%20HQ`);
    expect(reportingManagerListEndpoint(BASE, "", false)).toBe(BASE);
  });
});

describe("reportingApproverListEndpoint", () => {
  it("offers the COO, branch HR and Branch Admin for a manager role", () => {
    expect(reportingApproverListEndpoint(BASE, "Mumbai HQ", true)).toBe(`${BASE}?manager_approvers=1&branch=Mumbai%20HQ`);
    expect(reportingApproverListEndpoint(BASE, "", true)).toBe(`${BASE}?manager_approvers=1`);
  });

  it("keeps the existing list for other roles", () => {
    expect(reportingApproverListEndpoint(BASE, "Mumbai HQ", false)).toBe(`${BASE}?branch=Mumbai%20HQ`);
    expect(reportingApproverListEndpoint(BASE, "", false)).toBe(BASE);
  });
});

describe("Manager designation in the eligible-list endpoint", () => {
  it("passes the Manager's own designation so a COO / CMD is not offered branch HR by designation", () => {
    expect(reportingManagerListEndpoint(BASE, "Surat", true, "COO")).toBe(`${BASE}?manager_approvers=1&branch=Surat&designation=COO`);
    expect(reportingApproverListEndpoint(BASE, "", true, "Hr. Manager")).toBe(`${BASE}?manager_approvers=1&designation=Hr.%20Manager`);
  });

  it("omits an empty designation and ignores it for other roles", () => {
    expect(reportingManagerListEndpoint(BASE, "Surat", true, "")).toBe(`${BASE}?manager_approvers=1&branch=Surat`);
    expect(reportingApproverListEndpoint(BASE, "Surat", false, "COO")).toBe(`${BASE}?branch=Surat`);
  });
});

describe("shouldClearReportingManager", () => {
  const base = { managerRoleNames: MANAGER_ROLES, eligibleIds: ["coo-1"] };

  it("clears a non-COO manager when the role changes to a manager role", () => {
    expect(shouldClearReportingManager({ ...base, previousRole: "employee", nextRole: "manager", reportingManagerId: "mgr-9" })).toBe(true);
  });

  it("keeps the COO when the role changes to a manager role", () => {
    expect(shouldClearReportingManager({ ...base, previousRole: "employee", nextRole: "manager", reportingManagerId: "coo-1" })).toBe(false);
  });

  it("never touches an existing manager's stored value (no role change)", () => {
    expect(shouldClearReportingManager({ ...base, previousRole: "manager", nextRole: "manager__team_lead", reportingManagerId: "mgr-9" })).toBe(false);
  });

  it("leaves non-manager roles alone", () => {
    expect(shouldClearReportingManager({ ...base, previousRole: "manager", nextRole: "employee", reportingManagerId: "mgr-9" })).toBe(false);
  });

  it("does nothing when no reporting manager is set", () => {
    expect(shouldClearReportingManager({ ...base, previousRole: "employee", nextRole: "manager", reportingManagerId: "" })).toBe(false);
  });

  it("clears when the eligible list hasn't loaded yet rather than risk an invalid save", () => {
    expect(shouldClearReportingManager({ ...base, eligibleIds: null, previousRole: "employee", nextRole: "manager", reportingManagerId: "mgr-9" })).toBe(true);
  });
});
