import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { DayRecord } from "@/types/attendance";
import EssAttendanceCalendar, { dayClass } from "./EssAttendanceCalendar";

function record(status: string, extra: Partial<DayRecord> = {}): DayRecord {
  return {
    date: "", status, color: "#000000", clockIn: null, clockOut: null, hours: null, note: null,
    canRegularize: false, regularization_required: false, ...extra,
  };
}

const noop = () => {};

function render(year: number, month: number, calendar: Record<string, DayRecord> = {}, isLoading = false): string {
  return renderToStaticMarkup(
    <EssAttendanceCalendar
      year={year} month={month} calendar={calendar} isLoading={isLoading}
      onPreviousMonth={noop} onNextMonth={noop} onToday={noop}
    />,
  );
}

/** The cells of each row, as "", "1", "2", … in grid order. */
function cellDays(html: string): string[][] {
  const rows = html.split('role="row"').slice(2); // skip the text before the first row and the weekday row
  return rows.map(row => {
    const cells = row.split('role="cell"').slice(1);
    return cells.map(cell => cell.match(/class="ess-cal-date"[^>]*>(\d+)</)?.[1] ?? "");
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(2026, 10, 11, 10, 0, 0)); // 11 November 2026
});
afterEach(() => vi.useRealTimers());

describe("EssAttendanceCalendar", () => {
  it("shows the month and year, Sunday-first weekday headers and the navigation controls", () => {
    const html = render(2026, 8);
    expect(html).toContain("August 2026");
    const headers = [...html.matchAll(/role="columnheader">(\w+)</g)].map(match => match[1]);
    expect(headers).toEqual(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]);
    expect(html).toContain('aria-label="Previous month"');
    expect(html).toContain('aria-label="Next month"');
    expect(html).toContain(">Today</button>");
  });

  it("lays out a month starting on Saturday in six rows with the 1st under Saturday", () => {
    const rows = cellDays(render(2026, 8));
    expect(rows).toHaveLength(6);
    expect(rows[0]).toEqual(["", "", "", "", "", "", "1"]);
    expect(rows[5]).toEqual(["30", "31", "", "", "", "", ""]);
  });

  it("lays out a month starting on Sunday with the 1st in the first column", () => {
    const rows = cellDays(render(2026, 3));
    expect(rows[0]).toEqual(["1", "2", "3", "4", "5", "6", "7"]);
  });

  it("lays out a month starting on Monday with one blank before the 1st", () => {
    const rows = cellDays(render(2026, 6));
    expect(rows[0]).toEqual(["", "1", "2", "3", "4", "5", "6"]);
  });

  it("shows each day's status as a coloured dot and label from the attendance data", () => {
    const html = render(2026, 11, {
      "2": record("Present", { clockIn: "09:05", clockOut: "18:10" }),
      "3": record("Late"),
      "4": record("Absent"),
      "5": record("Half Day"),
      "6": record("On Leave"),
      "8": record("Weekly Off"),
      "9": record("Holiday", { holiday_name: "Founders Day" }),
      "10": record("Missing Clock Out"),
      "12": record("Not Joined"),
    });
    for (const [className, label] of [
      ["present", "Present"], ["late", "Late"], ["absent", "Absent"], ["half-day", "Half Day"],
      ["leave", "On Leave"], ["weekly-off", "Weekly Off"], ["holiday", "Founders Day"],
      ["incomplete", "Missing Clock Out"],
    ]) {
      expect(html).toContain(`ess-status-dot ${className}" aria-hidden="true"></i><span class="ess-cal-label">${label}</span>`);
    }
    // Days outside the employment window render blank.
    expect(html).not.toContain("Not Joined");
    expect(html).toContain("2 November 2026 — Present — In 09:05 · Out 18:10");
  });

  it("tints working-day cells in their status colour; week-offs and holidays get the muted tint; blank days stay plain", () => {
    const html = render(2026, 11, { "2": record("Present"), "4": record("Absent"), "8": record("Weekly Off") });
    expect(html).toMatch(/class="ess-cal-cell st-present"[^>]*data-date="2026-11-02"/);
    expect(html).toMatch(/class="ess-cal-cell st-absent"[^>]*data-date="2026-11-04"/);
    expect(html).toMatch(/class="ess-cal-cell non-working"[^>]*data-date="2026-11-08"/);
    expect(html).toMatch(/class="ess-cal-cell"[^>]*data-date="2026-11-03"/);
  });

  it("marks today and disables the Today button while the current month is shown", () => {
    const html = render(2026, 11);
    expect(html).toMatch(/class="ess-cal-cell today"[^>]*data-date="2026-11-11"/);
    expect(html).toContain('aria-current="date">11<');
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Today<\/button>/);
  });

  it("enables the Today button and marks no day as today in another month", () => {
    const html = render(2026, 8);
    expect(html).not.toContain('aria-current="date"');
    expect(html).not.toMatch(/<button[^>]*disabled=""[^>]*>Today<\/button>/);
  });

  it("disables navigation while the month is loading", () => {
    const html = render(2026, 8, {}, true);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*aria-label="Previous month"/);
    expect(html).toContain('aria-busy="true"');
  });
});

describe("dayClass", () => {
  it("keeps the existing status-to-colour mapping", () => {
    expect(dayClass("Present")).toBe("present");
    expect(dayClass("Late")).toBe("late");
    expect(dayClass("Absent")).toBe("absent");
    expect(dayClass("Half Day")).toBe("half-day");
    expect(dayClass("On Leave")).toBe("leave");
    expect(dayClass("Sick Leave")).toBe("leave");
    expect(dayClass("Weekly Off")).toBe("weekly-off");
    expect(dayClass("Holiday")).toBe("holiday");
    expect(dayClass("Incomplete")).toBe("incomplete");
    expect(dayClass("Missing Clock Out")).toBe("incomplete");
    expect(dayClass("Not Joined")).toBe("not-joined");
    expect(dayClass(undefined)).toBe("unrecorded");
  });
});

describe("EssAttendanceCalendar work from home", () => {
  it("tags a day worked from home, keeping its status, and explains the tag in the title and the legend", () => {
    const html = render(2026, 11, { "16": record("Late", { work_mode: "wfh", clockIn: "13:04" }) });
    expect(html).toContain("ess-cal-label\">Late<");
    expect(html).toMatch(/class="ess-cal-wfh" title="Work from home"/);
    expect(html).toContain("16 November 2026 — Late — Work from home — In 13:04");
    expect(html).toContain("Work from home</span>");   // the legend entry
  });

  it("does not tag office days or days with no record", () => {
    const html = render(2026, 11, { "17": record("Present", { work_mode: "office" }), "18": record("Late") });
    const cells = html.split('role="cell"');
    const tagged = cells.filter(cell => cell.includes('title="Work from home"'));
    expect(tagged).toHaveLength(0);
  });
});

describe("EssAttendanceCalendar hours not completed", () => {
  it("tags a Present day that fell short of a full day with the minutes short, keeping its status", () => {
    const html = render(2026, 11, { "10": record("Present", { short_minutes: 80, short_display: "1h 20m", clockIn: "09:12" }) });
    expect(html).toContain("ess-cal-label\">Present<");
    expect(html).toMatch(/class="ess-cal-short" title="Hours not completed: short by 1h 20m"/);
    expect(html).toContain("Short 1h 20m");
    expect(html).toContain("10 November 2026 — Present — Hours not completed (short by 1h 20m) — In 09:12");
    expect(html).toContain("Hours not completed</span>");   // the legend entry
  });

  it("does not tag completed days, half days or days with no record", () => {
    const html = render(2026, 11, {
      "10": record("Present", { short_minutes: 0, short_display: null }),
      "11": record("Half Day"),
    });
    const cells = html.split('role="cell"');
    expect(cells.filter(cell => cell.includes('title="Hours not completed'))).toHaveLength(0);
  });

  it("can show both tags on one day", () => {
    const html = render(2026, 11, { "10": record("Late", { work_mode: "wfh", short_minutes: 30, short_display: "30m" }) });
    expect(html).toContain('title="Work from home"');
    expect(html).toContain("Short 30m");
  });
});

/** The inline legend (the coloured key under the heading), not the "What do these mean?" list below it. */
function inlineLegend(html: string): string {
  const start = html.indexOf('class="ess-calendar-legend"');
  const end = html.indexOf("<details", start);
  return html.slice(start, end);
}

describe("EssAttendanceCalendar legend", () => {
  it("lists only the colours that appear in the month shown", () => {
    const legend = inlineLegend(render(2026, 11, {
      "10": record("Present"), "11": record("Late"), "14": record("Weekly Off"),
    }));
    expect(legend).toContain("Present");
    expect(legend).toContain("Late");
    expect(legend).toContain("Week off / Holiday");
    for (const absent of ["Absent", "Half day", "On leave", "Incomplete", "Work from home", "Hours not completed"]) {
      expect(legend).not.toContain(absent);
    }
  });

  it("shows no legend entries for a month with nothing recorded, but still offers the full key", () => {
    const html = render(2026, 11, {});
    expect(inlineLegend(html)).not.toContain("ess-status-dot");
    expect(html).toContain("What do these mean?");
  });

  it("explains every colour and both tags in plain words in the key, including Incomplete", () => {
    const html = render(2026, 11, {});
    const key = html.slice(html.indexOf("<details"));
    for (const label of ["Present", "Late", "Absent", "Half day", "On leave", "Week off / Holiday", "Incomplete", "Work from home", "Hours not completed"]) {
      expect(key).toContain(label);
    }
    expect(key).toContain("Punched in but never punched out");
    expect(key).toContain("Raise a correction");
  });

  it("does not count days before joining as a legend entry", () => {
    const legend = inlineLegend(render(2026, 11, { "2": record("Not Employed"), "10": record("Present") }));
    expect(legend).toContain("Present");
    expect(legend).not.toContain("Week off / Holiday");
  });

  it("draws the tags as spans, never as italic <i> elements, and stacks the two tags together in one block", () => {
    const html = render(2026, 11, { "10": record("Late", { work_mode: "wfh", short_minutes: 30, short_display: "30m" }) });
    expect(html).not.toMatch(/<i class="ess-cal-(wfh|short)"/);
    expect(html).toMatch(/<div class="ess-cal-tags"><span class="ess-cal-wfh"[\s\S]*<span class="ess-cal-short"/);
  });

  it("adds no tags block to a day without tags", () => {
    expect(render(2026, 11, { "10": record("Present") })).not.toContain("ess-cal-tags");
  });

  it("tags a day that was Present only because the full hours were worked, with who and when, and explains it in the legend", () => {
    const html = render(2026, 11, {
      "10": record("Present", { clockIn: "10:14", clockOut: "19:20", is_late: true, late_forgiven: true, late_after: "09:15" }),
      "11": record("Present", { clockIn: "09:05", clockOut: "18:10" }),
      "12": record("Late", { clockIn: "10:30", is_late: true }),
    });
    expect(html.match(/class="ess-cal-late"/g)?.length).toBeGreaterThanOrEqual(3);   // cell tag + legend + key (once each)
    expect(html).toContain("Late login");
    expect(html).toContain("Punched in 10:14 (after 09:15).");
    expect(html).not.toContain("Full hours were completed");
    // The on-time Present day and the day that is simply Late get no tag.
    const cellFor = (day: string) => html.split('role="cell"').find(cell => cell.includes(`class="ess-cal-date"`) && new RegExp(`class="ess-cal-date"[^>]*>${day}<`).test(cell)) ?? "";
    expect(cellFor("10")).toContain("ess-cal-late");
    expect(cellFor("11")).not.toContain("ess-cal-late");
    expect(cellFor("12")).not.toContain("ess-cal-late");
  });

  it("shows no late-login tag or legend entry in a month with none", () => {
    const html = render(2026, 11, { "10": record("Present", { clockIn: "09:00", clockOut: "18:00" }) });
    expect(html).not.toContain("Arrived late, full day worked");              // the legend lists only what the month has
    expect(html.match(/class="ess-cal-late"/g)?.length).toBe(1);               // only the always-present "What do these mean?" row
  });
});
