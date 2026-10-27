import { afterEach, describe, expect, it } from "vitest";
import { isEmployeeUuid, setViewAsEmployee, viewAsHeaderFor, viewWorkspacePath } from "./viewAs";

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

  it("only accepts a real employee id", () => {
    expect(isEmployeeUuid(EMPLOYEE)).toBe(true);
    expect(isEmployeeUuid("EMP00081")).toBe(false);
    expect(isEmployeeUuid(undefined)).toBe(false);
  });
});
