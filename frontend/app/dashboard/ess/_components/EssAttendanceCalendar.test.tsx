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
      ["incomplete", "Missing Clock Out"], ["not-joined", "Not Joined"],
    ]) {
      expect(html).toContain(`ess-status-dot ${className}" aria-hidden="true"></i><span class="ess-cal-label">${label}</span>`);
    }
    expect(html).toContain("2 November 2026 — Present — In 09:05 · Out 18:10");
  });

  it("does not fill working days with a background colour; only week-offs and holidays get the muted tint", () => {
    const html = render(2026, 11, { "2": record("Present"), "8": record("Weekly Off") });
    expect(html).toMatch(/class="ess-cal-cell"[^>]*data-date="2026-11-02"/);
    expect(html).toMatch(/class="ess-cal-cell non-working"[^>]*data-date="2026-11-08"/);
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
