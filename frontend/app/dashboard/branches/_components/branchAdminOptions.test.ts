import { describe, expect, it } from "vitest";
import { findCurrentAdmin } from "./branchAdminOptions";
import type { ApiEmployeeOption, BranchAdminSeat } from "./_data";

// Employee record: `id` is the employee code, `uuid` the User pk. Position: `holder` is the User pk.
const employee = (uuid: string, employeeId: string, branch = "Sria"): ApiEmployeeOption => ({
  id: employeeId, uuid, employee_id: employeeId, full_name: `Person ${employeeId}`, email: `${employeeId}@example.test`, branch,
});
const seat = (id: string, holder: string | null): BranchAdminSeat => ({
  id, title: "Branch Admin", org_unit_name: "Ops", holder, holder_employee_id: holder ? `code-${holder}` : null, holder_name: null,
});

describe("findCurrentAdmin", () => {
  it("returns the seat holder who works in this Company Code, with their seat", () => {
    const holders = [employee("u-1", "E001", "Pune"), employee("u-2", "E002")];
    expect(findCurrentAdmin([seat("p-1", "u-1"), seat("p-2", "u-2")], holders, "Sria")).toEqual({
      employee: holders[1], positionId: "p-2", positionTitle: "Branch Admin — Ops",
    });
  });

  it("matches the seat holder on the User pk, not the employee code", () => {
    expect(findCurrentAdmin([seat("p-1", "E001")], [employee("u-1", "E001")], "Sria")).toBeNull();
  });

  it("ignores a seat holder who works in another Company Code", () => {
    expect(findCurrentAdmin([seat("p-1", "u-1")], [employee("u-1", "E001", "Pune")], "Sria")).toBeNull();
  });

  it("returns null when every seat is vacant", () => {
    expect(findCurrentAdmin([seat("p-1", null)], [employee("u-1", "E001")], "Sria")).toBeNull();
  });
});
