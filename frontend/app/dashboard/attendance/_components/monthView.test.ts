import { describe, expect, it } from "vitest";
import {
  barSegments, buildGrid, canMark, countByStatus, currentMonthISO, dayTiming, daySentence, defaultSelectedDate, effectiveStatus, filterEmployees, hoursBarPercent, localISODate, monthInsights, shiftMonth, timeRangeLabel, type DayRecord,
} from "./monthView";

function day(date: string, status: string, overrides: Partial<DayRecord> = {}): DayRecord {
  return {
    date, day_short: "", day_num: Number(date.slice(8)), status, status_label: status, clock_in: null, clock_out: null,
    total_hours: 0, is_flagged: false, record_id: status === "no_record" || status === "weekly_off" || status === "absent" ? null : `r-${date}`, ...overrides,
  };
}

// November 2026: Sunday the 1st. Today is Wednesday the 18th.
const TODAY = "2026-11-18";
const nov = (n: number) => `2026-11-${String(n).padStart(2, "0")}`;

describe("dates", () => {
  it("uses the local calendar date, not UTC", () => {
    expect(localISODate(new Date(2026, 10, 18, 0, 30))).toBe("2026-11-18");
    expect(currentMonthISO(new Date(2026, 11, 1, 0, 5))).toBe("2026-12");
  });
  it("moves between months across a year end", () => {
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
  });
  it("classifies a day as past, today or future", () => {
    expect([dayTiming(nov(17), TODAY), dayTiming(nov(18), TODAY), dayTiming(nov(19), TODAY)]).toEqual(["past", "today", "future"]);
  });
});

describe("buildGrid", () => {
  it("starts on Monday: November 2026 begins on a Sunday, so six empty cells come first", () => {
    const days = Array.from({ length: 30 }, (_, index) => day(nov(index + 1), "no_record"));
    const weeks = buildGrid(days, "2026-11");
    expect(weeks).toHaveLength(6);   // 6 blank cells + 30 days = 36 cells = six rows
    expect(weeks[0].slice(0, 6).every(cell => cell === null)).toBe(true);
    expect(weeks[0][6]?.day_num).toBe(1);
    expect(weeks.every(week => week.length === 7)).toBe(true);
  });
});

describe("canMark", () => {
  it("allows a past or current day with no record and never a future day or a day that already has one", () => {
    expect(canMark(day(nov(10), "absent"), TODAY)).toBe(true);
    expect(canMark(day(nov(18), "no_record"), TODAY)).toBe(true);
    expect(canMark(day(nov(25), "no_record"), TODAY)).toBe(false);
    expect(canMark(day(nov(11), "present"), TODAY)).toBe(false);
  });
});

describe("monthInsights", () => {
  const days = [
    day(nov(2), "present", { total_hours: 9 }), day(nov(3), "late", { total_hours: 8 }), day(nov(4), "half_day", { total_hours: 4 }),
    day(nov(5), "absent"), day(nov(6), "on_leave"), day(nov(7), "weekly_off"), day(nov(8), "holiday"),
    day(nov(9), "no_record"), day(nov(25), "no_record"),   // the 25th is in the future
  ];

  it("counts only working days up to today, and measures attendance and average hours over the days worked", () => {
    const insights = monthInsights(days, TODAY);
    expect(insights.workingDays).toBe(6);                // 2,3,4,5,6,9 (week off, holiday and the future day are left out)
    expect(insights.worked).toBe(3);
    expect(insights.attendancePercent).toBe(50);
    expect(insights.averageHours).toBe(7);              // (9 + 8 + 4) / 3
    expect(insights.unrecorded).toBe(1);                // the 9th has no record at all
  });

  it("has nothing to measure before a working day has passed", () => {
    const insights = monthInsights([day(nov(25), "no_record")], TODAY);
    expect([insights.workingDays, insights.attendancePercent, insights.averageHours]).toEqual([0, null, null]);
  });
});

describe("barSegments and counts", () => {
  it("shows each status's share of the working days so far and leaves out empty ones", () => {
    const days = [day(nov(2), "present"), day(nov(3), "present"), day(nov(4), "absent"), day(nov(7), "weekly_off"), day(nov(9), "no_record"), day(nov(25), "no_record")];
    expect(barSegments(days, TODAY)).toEqual([{ status: "present", count: 2 }, { status: "absent", count: 1 }, { status: "no_record", count: 1 }]);
    expect(countByStatus(days, TODAY)).toEqual({ present: 2, absent: 1, weekly_off: 1, no_record: 1, future: 1 });   // the 25th has not happened yet
  });
});

describe("effectiveStatus", () => {
  it("shows a day with no record as Not marked once it has happened and Upcoming before, and leaves real statuses alone", () => {
    expect(effectiveStatus(day(nov(9), "no_record"), TODAY)).toBe("no_record");
    expect(effectiveStatus(day(nov(18), "no_record"), TODAY)).toBe("no_record");
    expect(effectiveStatus(day(nov(25), "no_record"), TODAY)).toBe("future");
    expect(effectiveStatus(day(nov(25), "on_leave"), TODAY)).toBe("on_leave");
  });
  it("draws the hours bar on a 10-hour scale, never past full width", () => {
    expect([hoursBarPercent(0), hoursBarPercent(5), hoursBarPercent(9.1), hoursBarPercent(14)]).toEqual([0, 50, 91, 100]);
  });
});

describe("timeRangeLabel", () => {
  it("shows both times, 'still in', or nothing", () => {
    expect(timeRangeLabel({ clock_in: "09:05", clock_out: "18:10" })).toBe("09:05 – 18:10");
    expect(timeRangeLabel({ clock_in: "09:05", clock_out: null })).toBe("09:05 – still in");
    expect(timeRangeLabel({ clock_in: null, clock_out: null })).toBe("");
  });
});

describe("defaultSelectedDate", () => {
  const days = [day(nov(2), "present"), day(nov(3), "present"), day(nov(9), "no_record"), day(nov(25), "no_record")];
  it("opens on today when it is in the month, else on the latest recorded day, else on the first day", () => {
    expect(defaultSelectedDate(days, TODAY)).toBe(nov(3));   // no day is today (the 18th is missing), so the latest recorded day
    expect(defaultSelectedDate([...days, day(nov(18), "no_record")], TODAY)).toBe(nov(18));
    expect(defaultSelectedDate(days, "2026-12-05")).toBe(nov(3));
    expect(defaultSelectedDate([day(nov(9), "no_record")], "2026-12-05")).toBe(nov(9));
    expect(defaultSelectedDate([], TODAY)).toBeNull();
  });
});

describe("daySentence", () => {
  it("says one plain sentence per kind of day", () => {
    expect(daySentence({ total_hours: 9.1 }, "present")).toBe("Present, 9.1h worked.");
    expect(daySentence({ total_hours: 8 }, "late")).toBe("Arrived late. 8h worked.");
    expect(daySentence({ total_hours: 0 }, "absent")).toBe("Marked absent.");
    expect(daySentence({ total_hours: 0 }, "no_record")).toBe("Nothing is recorded for this day yet.");
    expect(daySentence({ total_hours: 0 }, "future")).toBe("This day has not happened yet.");
    expect(daySentence({ total_hours: 0 }, "holiday")).toBe("Public holiday.");
  });
});

describe("filterEmployees", () => {
  const people = [
    { id: "1", employee_id: "EMP001", full_name: "Asha Rao", department: "Finance", designation: "Analyst" },
    { id: "2", employee_id: "EMP002", full_name: "Durga Gadde", department: "Web", designation: "Lead" },
    { id: "3", employee_id: "10000003", full_name: "Kabir Rao", department: "Finance", designation: "Manager" },
  ];
  it("returns everyone when nothing (or only spaces) is typed", () => {
    expect(filterEmployees(people, "")).toHaveLength(3);
    expect(filterEmployees(people, "   ")).toHaveLength(3);
  });
  it("matches a name, an ID, a department or a designation, in any case", () => {
    expect(filterEmployees(people, "durga").map(person => person.id)).toEqual(["2"]);
    expect(filterEmployees(people, "emp001").map(person => person.id)).toEqual(["1"]);
    expect(filterEmployees(people, "FINANCE").map(person => person.id)).toEqual(["1", "3"]);
    expect(filterEmployees(people, "lead").map(person => person.id)).toEqual(["2"]);
  });
  it("needs every word typed to match, so more words narrow the list", () => {
    expect(filterEmployees(people, "rao finance").map(person => person.id)).toEqual(["1", "3"]);
    expect(filterEmployees(people, "rao manager").map(person => person.id)).toEqual(["3"]);
    expect(filterEmployees(people, "rao web")).toEqual([]);
  });
});
