// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, renderHook } from "@testing-library/react";
import type { WorkStatusAssignment } from "@/types/workStatus";

const useFetchSpy = vi.fn();
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string) => { useFetchSpy(url); return { data: null, loading: false, error: null, status: null, refetch: vi.fn() }; },
}));

import { useWorkStatus } from "./useWorkStatus";
import { initialForm, validateForm, EMPTY_FORM } from "./useProjectAssignmentActions";

beforeEach(() => { useFetchSpy.mockReset(); });
afterEach(() => { cleanup(); });

describe("useWorkStatus", () => {
  it("asks for the signed-in employee's own work status by default", () => {
    renderHook(() => useWorkStatus());
    expect(useFetchSpy).toHaveBeenCalledWith("/work-status/me/?page=1");
  });

  it("asks for another employee's when given one", () => {
    renderHook(() => useWorkStatus("EMP00021", 2));
    expect(useFetchSpy).toHaveBeenCalledWith("/work-status/EMP00021/?page=2");
  });
});

const ASSIGNMENT: WorkStatusAssignment = {
  assignment_id: 7, project_id: 3, project_code: "", project_name: "Website Revamp", role: "Developer", notes: "",
  work_mode: "office", work_mode_display: "Work From Office (WFO)", work_location: "",
  start_date: "2026-11-01", end_date: "2026-12-31", assignment_status: "active", assignment_status_display: "Active",
  is_current: true, is_upcoming: false, days_left: 35, is_ending_soon: false, last_change: null, change_log: [],
};

describe("project assignment form", () => {
  it("starts blank when assigning and from the assignment when editing", () => {
    expect(initialForm("assign", ASSIGNMENT)).toEqual(EMPTY_FORM);
    expect(initialForm("edit", ASSIGNMENT).project_name).toBe("Website Revamp");
    expect(initialForm("extend", ASSIGNMENT).end_date).toBe("");
  });

  it("needs a project name and both dates in order to assign", () => {
    const form = { ...EMPTY_FORM, project_name: "X", start_date: "2026-12-10", end_date: "2026-12-01" };
    expect(validateForm("assign", { ...form, project_name: " " }, null)).toBe("Enter the project name.");
    expect(validateForm("assign", { ...form, end_date: "" }, null)).toBe("End date is required.");
    expect(validateForm("assign", form, null)).toBe("End date cannot be before the start date.");
    expect(validateForm("assign", { ...form, end_date: "2026-12-20" }, null)).toBe("");
  });

  it("needs the place when the work mode is Client Location", () => {
    const form = { ...EMPTY_FORM, project_name: "X", start_date: "2026-12-01", end_date: "2026-12-20", work_mode: "client_site" as const };
    expect(validateForm("assign", form, null)).toBe("Enter the client location (address or site name).");
    expect(validateForm("assign", { ...form, work_location: "Client HQ, Pune" }, null)).toBe("");
    expect(validateForm("assign", { ...form, work_mode: "home" as const }, null)).toBe("");
  });

  it("only lets Extend move the end date later and End move it earlier", () => {
    expect(validateForm("extend", { ...EMPTY_FORM, end_date: "2026-12-31" }, ASSIGNMENT)).not.toBe("");
    expect(validateForm("extend", { ...EMPTY_FORM, end_date: "2027-01-31" }, ASSIGNMENT)).toBe("");
    expect(validateForm("end", { ...EMPTY_FORM, end_date: "2027-01-31" }, ASSIGNMENT)).toBe("To move the end date later, use Extend.");
    expect(validateForm("end", EMPTY_FORM, ASSIGNMENT)).toBe("");
  });
});
