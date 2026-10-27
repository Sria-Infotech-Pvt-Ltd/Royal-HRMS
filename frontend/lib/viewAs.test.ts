import { afterEach, describe, expect, it } from "vitest";
import { adminProfilePath, isViewAsTarget, setViewAsEmployee, viewAsHeaderFor, viewWorkspacePath } from "./viewAs";

const EMPLOYEE = "7f9c1d2e-3a4b-4c5d-8e6f-0123456789ab";

describe("view as employee", () => {
  afterEach(() => setViewAsEmployee(null));

  it("adds no header unless an employee is being viewed", () => {
    expect(viewAsHeaderFor("/employees/me/")).toBeNull();
  });

  it("adds the employee's id to ordinary calls while viewing", () => {
    setViewAsEmployee(EMPLOYEE);
    expect(viewAsHeaderFor("/employees/me/")).toEqual({ name: "X-View-As-Employee", value: EMPLOYEE });
    expect(viewAsHeaderFor("/payroll/payslips/my/")).toEqual({ name: "X-View-As-Employee", value: EMPLOYEE });
  });

  it("keeps notifications and session calls as the signed-in person", () => {
    setViewAsEmployee(EMPLOYEE);
    expect(viewAsHeaderFor("/notifications/unread-count/")).toBeNull();
    expect(viewAsHeaderFor("/token/refresh/")).toBeNull();
  });

  it("builds the workspace address for an employee", () => {
    expect(viewWorkspacePath(EMPLOYEE)).toBe(`/dashboard/ess?as=${EMPLOYEE}`);
  });

  it("accepts an employee id or an employee code, and nothing else", () => {
    expect(isViewAsTarget(EMPLOYEE)).toBe(true);
    expect(isViewAsTarget("EMP00081")).toBe(true);
    expect(isViewAsTarget("UAT26-050")).toBe(true);
    expect(isViewAsTarget("../../etc")).toBe(false);
    expect(isViewAsTarget("a b")).toBe(false);
    expect(isViewAsTarget(undefined)).toBe(false);
  });

  it("builds the workspace address from an employee code and the admin profile address", () => {
    expect(viewWorkspacePath("EMP00081")).toBe("/dashboard/ess?as=EMP00081");
    expect(adminProfilePath("EMP00081")).toBe("/dashboard/employees/EMP00081?view=profile");
  });
});
