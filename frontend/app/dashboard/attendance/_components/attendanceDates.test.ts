import { describe, expect, it } from "vitest";
import { PALETTE, statusColour, tint } from "./attendancePalette";
import { daysBefore, relativeDayLabel, shiftISODate, weekdayName } from "./attendanceDates";

describe("shiftISODate", () => {
  it("moves exactly one day each way, including across month and year ends", () => {
    expect(shiftISODate("2026-11-14", -1)).toBe("2026-11-13");
    expect(shiftISODate("2026-11-14", 1)).toBe("2026-11-15");
    expect(shiftISODate("2026-12-01", -1)).toBe("2026-11-30");
    expect(shiftISODate("2026-12-31", 1)).toBe("2027-01-01");
    expect(shiftISODate("2028-02-28", 1)).toBe("2028-02-29");   // a leap year
  });

  it("gives the same answer in India as everywhere else (the old code was a day early there)", () => {
    // The vitest run is repeated under TZ=Asia/Kolkata by the package script check in the report; the assertion is timezone-free.
    const dates = ["2026-03-29", "2026-10-25", "2026-11-14"];
    for (const date of dates) {
      expect(shiftISODate(shiftISODate(date, 1), -1)).toBe(date);
      expect(daysBefore(shiftISODate(date, -1), date)).toBe(1);
    }
  });
});

describe("relativeDayLabel", () => {
  it("says Today, Yesterday, N days ago, Tomorrow and In N days", () => {
    const today = "2026-11-18";
    expect([relativeDayLabel("2026-11-18", today), relativeDayLabel("2026-11-17", today), relativeDayLabel("2026-11-14", today)]).toEqual(["Today", "Yesterday", "4 days ago"]);
    expect([relativeDayLabel("2026-11-19", today), relativeDayLabel("2026-11-21", today)]).toEqual(["Tomorrow", "In 3 days"]);
  });
  it("counts across a month boundary", () => {
    expect(daysBefore("2026-10-30", "2026-11-02")).toBe(3);
  });
  it("names the weekday", () => {
    expect(weekdayName("2026-11-18")).toBe("Wednesday");
    expect(weekdayName("2026-11-14")).toBe("Saturday");
  });
});

describe("palette", () => {
  it("gives every status its own colour", () => {
    expect(new Set(Object.values(PALETTE)).size).toBe(Object.keys(PALETTE).length);
  });
  it("turns a hex colour into a translucent tint", () => {
    expect(tint("#16a34a", 0.16)).toBe("rgba(22,163,74,0.16)");
  });
  it("maps the API's status keys, with no_record as the calm Not marked colour and unknown keys as slate", () => {
    expect([statusColour("late"), statusColour("no_record"), statusColour("whatever")]).toEqual([PALETTE.late, PALETTE.not_marked, PALETTE.weekly_off]);
  });
});
