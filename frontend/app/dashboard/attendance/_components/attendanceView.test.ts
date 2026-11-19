import { describe, expect, it } from "vitest";
import { STATUS_TABS, isBlank, nextSort, summariseTimes, tabCount } from "./attendanceView";

const chips = { present: 3, late: 1, wfh: 0, absent: 11, on_leave: 2, half_day: 0, weekly_off: 4, holiday: 0 };

describe("tabCount", () => {
  it("gives each status its own number and leaves All without one", () => {
    expect(tabCount("", chips)).toBeNull();
    expect(tabCount("absent", chips)).toBe(11);
    expect(tabCount("half_day", chips)).toBe(0);
  });
  it("shows 0 while the numbers are still loading", () => {
    expect(tabCount("present", undefined)).toBe(0);
  });
  it("lists All first and then the seven statuses the server can filter on", () => {
    expect(STATUS_TABS.map(tab => tab.key)).toEqual(["", "present", "late", "wfh", "absent", "on_leave", "half_day", "weekly_off"]);
  });
});

describe("nextSort", () => {
  it("sorts a new column ascending and flips the one already sorted", () => {
    expect(nextSort({ by: "name", dir: "asc" }, "status")).toEqual({ by: "status", dir: "asc" });
    expect(nextSort({ by: "name", dir: "asc" }, "name")).toEqual({ by: "name", dir: "desc" });
    expect(nextSort({ by: "name", dir: "desc" }, "name")).toEqual({ by: "name", dir: "asc" });
  });
});

describe("summariseTimes", () => {
  it("knows a day with no punches, with only a clock-in, and with both", () => {
    expect(summariseTimes("—", "—").kind).toBe("none");
    expect(summariseTimes("09:05", "—")).toEqual({ kind: "partial", clockIn: "09:05", clockOut: "—" });
    expect(summariseTimes("09:05", "18:10")).toEqual({ kind: "full", clockIn: "09:05", clockOut: "18:10" });
  });
  it("treats an empty string like a missing time", () => {
    expect(summariseTimes("", "").kind).toBe("none");
    expect(isBlank("—")).toBe(true);
    expect(isBlank("09:05")).toBe(false);
  });
});
