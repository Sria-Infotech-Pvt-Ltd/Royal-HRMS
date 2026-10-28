import { describe, expect, it } from "vitest";
import { ATTENDANCE_TAB_IDS, buildAttendanceSearch, parseAttendanceLocation } from "./attendanceTabs";

describe("attendance tab location", () => {
  it("reads every tab id from the URL, in any order", () => {
    for (const id of [...ATTENDANCE_TAB_IDS].reverse()) {
      expect(parseAttendanceLocation(`?tab=${id}`).tab).toBe(id);
    }
  });

  it("falls back to Attendance > Team Day View for a missing or unknown tab", () => {
    expect(parseAttendanceLocation("")).toEqual({ tab: "attendance", view: "team" });
    expect(parseAttendanceLocation("?tab=nonsense&view=weird")).toEqual({ tab: "attendance", view: "team" });
  });

  it("reads the Employee Month view", () => {
    expect(parseAttendanceLocation("?view=employee")).toEqual({ tab: "attendance", view: "employee" });
  });

  it("round-trips every tab and view through the query string", () => {
    for (const tab of ATTENDANCE_TAB_IDS) {
      for (const view of ["team", "employee"] as const) {
        const parsed = parseAttendanceLocation(buildAttendanceSearch("", { tab, view }));
        // the view only exists on the Attendance tab; elsewhere it resets to team
        expect(parsed).toEqual({ tab, view: tab === "attendance" ? view : "team" });
      }
    }
  });

  it("keeps unrelated params and drops defaults", () => {
    expect(buildAttendanceSearch("?employee=EMP001&month=2026-10", { tab: "ot", view: "team" })).toBe("?employee=EMP001&month=2026-10&tab=ot");
    expect(buildAttendanceSearch("?tab=ot&view=employee", { tab: "attendance", view: "team" })).toBe("");
  });
});
