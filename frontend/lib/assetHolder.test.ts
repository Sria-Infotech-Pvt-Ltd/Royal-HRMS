import { describe, expect, it } from "vitest";
import { holderView } from "./assetHolder";
import type { ActiveAssignment } from "@/types/assets";

const active = (over: Partial<ActiveAssignment> = {}): ActiveAssignment => ({
  id: "a1", status: "assigned", status_display: "Assigned", assigned_date: "2026-03-01",
  expected_return_date: "2027-02-28", employee_hidden: false, employee_name: "First Holder", employee_code: "HE1",
  ...over,
});

describe("holderView", () => {
  it("shows the current holder of an assigned asset", () => {
    expect(holderView({ status: "assigned", active_assignment: active() })).toEqual({
      kind: "assigned", employee: "First Holder", code: "HE1", hidden: false, status: "Assigned",
      assignedDate: "2026-03-01", expectedReturn: "2027-02-28",
    });
  });

  it("says not currently assigned for an available asset (including one returned earlier)", () => {
    expect(holderView({ status: "available", active_assignment: null })).toEqual({ kind: "none", message: "Not currently assigned." });
    expect(holderView({ status: "available" })).toEqual({ kind: "none", message: "Not currently assigned." });
  });

  it("flags an Assigned status with no active assignment record instead of guessing", () => {
    expect(holderView({ status: "assigned", active_assignment: null }).kind).toBe("none");
    expect(holderView({ status: "assigned", active_assignment: null })).toMatchObject({ message: expect.stringContaining("no active assignment") });
  });

  it("withholds employee details the viewer may not see, and handles missing details", () => {
    expect(holderView({ status: "assigned", active_assignment: active({ employee_hidden: true, employee_name: null, employee_code: null }) }))
      .toMatchObject({ employee: "Not visible to you", code: null, hidden: true });
    expect(holderView({ status: "assigned", active_assignment: active({ employee_name: null, employee_code: null }) }))
      .toMatchObject({ employee: "Employee details not available", code: null });
  });
});
