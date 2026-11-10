import { describe, expect, it } from "vitest";
import { addMonths, daysInMonth, localToday, periodEnd } from "./saasDates";

describe("addMonths — calendar months, never +30 days", () => {
  it.each([
    ["2027-01-15", 1, "2027-02-15"],
    ["2027-01-31", 1, "2027-02-28"],
    ["2028-01-31", 1, "2028-02-29"],   // leap year
    ["2027-03-31", 1, "2027-04-30"],
    ["2027-04-30", 1, "2027-05-30"],
    ["2027-05-31", 1, "2027-06-30"],
    ["2026-12-31", 1, "2027-01-31"],   // year rollover
    ["2026-11-09", 1, "2026-12-09"],
    ["2028-02-29", 12, "2029-02-28"],  // leap day + 1 year
    ["2027-01-15", 12, "2028-01-15"],
    ["2027-08-31", 6, "2028-02-29"],
  ])("%s + %i month(s) = %s", (start, months, end) => {
    expect(addMonths(start, months)).toBe(end);
  });

  it("returns blank for an invalid date", () => {
    expect(addMonths("", 1)).toBe("");
    expect(addMonths("2027-02-30", 1)).toBe("");
    expect(addMonths("15/01/2027", 1)).toBe("");
  });
});

describe("periodEnd", () => {
  it("monthly is one month, yearly is twelve, unset is blank", () => {
    expect(periodEnd("2027-01-31", "monthly")).toBe("2027-02-28");
    expect(periodEnd("2027-01-31", "yearly")).toBe("2028-01-31");
    expect(periodEnd("2027-01-31", "")).toBe("");
  });
});

describe("helpers", () => {
  it("daysInMonth handles leap years", () => {
    expect([daysInMonth(2027, 2), daysInMonth(2028, 2), daysInMonth(2100, 2), daysInMonth(2000, 2)])
      .toEqual([28, 29, 28, 29]);
  });

  it("localToday uses the local calendar date, not UTC", () => {
    expect(localToday(new Date(2027, 0, 5, 1, 30))).toBe("2027-01-05");
  });
});
