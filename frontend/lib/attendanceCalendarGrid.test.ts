import { describe, expect, it } from "vitest";
import { buildMonthGrid, daysInMonth, firstWeekday, isoDate, MIN_CALENDAR_ROWS, WEEKDAY_SHORT } from "./attendanceCalendarGrid";

/** The weekday column (0 = Sunday) a day lands in, and its row. */
function positionOf(grid: (number | null)[][], day: number): { row: number; column: number } {
  for (let row = 0; row < grid.length; row++) {
    const column = grid[row].indexOf(day);
    if (column >= 0) return { row, column };
  }
  throw new Error(`day ${day} not in grid`);
}

/** Every day of the month must sit under the weekday JavaScript's Date gives it. */
function expectEveryDayUnderItsWeekday(year: number, month: number) {
  const grid = buildMonthGrid(year, month);
  for (let day = 1; day <= daysInMonth(year, month); day++) {
    expect(positionOf(grid, day).column).toBe(new Date(year, month - 1, day).getDay());
  }
}

describe("buildMonthGrid", () => {
  it("uses Sunday-first weekday headings", () => {
    expect(WEEKDAY_SHORT).toEqual(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]);
  });

  it("puts the 1st in the Sunday column with no leading blanks (March 2026 starts on Sunday)", () => {
    expect(firstWeekday(2026, 3)).toBe(0);
    const grid = buildMonthGrid(2026, 3);
    expect(grid[0]).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(grid).toHaveLength(5);
    expect(grid[4]).toEqual([29, 30, 31, null, null, null, null]);
    expectEveryDayUnderItsWeekday(2026, 3);
  });

  it("leaves one blank before a month that starts on Monday (June 2026)", () => {
    expect(firstWeekday(2026, 6)).toBe(1);
    const grid = buildMonthGrid(2026, 6);
    expect(grid[0]).toEqual([null, 1, 2, 3, 4, 5, 6]);
    expect(grid).toHaveLength(5);
    expectEveryDayUnderItsWeekday(2026, 6);
  });

  it("needs six rows for a 31-day month that starts on Saturday (August 2026)", () => {
    expect(firstWeekday(2026, 8)).toBe(6);
    const grid = buildMonthGrid(2026, 8);
    expect(grid[0]).toEqual([null, null, null, null, null, null, 1]);
    expect(grid).toHaveLength(6);
    expect(grid[5]).toEqual([30, 31, null, null, null, null, null]);
    expectEveryDayUnderItsWeekday(2026, 8);
  });

  it("needs six rows for a 30-day month that starts on Saturday (November 2025)", () => {
    expect(firstWeekday(2025, 11)).toBe(6);
    const grid = buildMonthGrid(2025, 11);
    expect(grid).toHaveLength(6);
    expect(grid[5]).toEqual([30, null, null, null, null, null, null]);
  });

  it("needs six rows for a 31-day month that starts on Friday (May 2026)", () => {
    expect(firstWeekday(2026, 5)).toBe(5);
    expect(buildMonthGrid(2026, 5)).toHaveLength(6);
  });

  it("pads a four-week February to the minimum row count (February 2026 starts Sunday, 28 days)", () => {
    const grid = buildMonthGrid(2026, 2);
    expect(grid).toHaveLength(MIN_CALENDAR_ROWS);
    expect(grid[3]).toEqual([22, 23, 24, 25, 26, 27, 28]);
    expect(grid[4].every(cell => cell === null)).toBe(true);
  });

  it("handles a leap-year February (February 2028 has 29 days)", () => {
    expect(daysInMonth(2028, 2)).toBe(29);
    expectEveryDayUnderItsWeekday(2028, 2);
    expect(buildMonthGrid(2028, 2).flat().filter(cell => cell !== null)).toHaveLength(29);
  });

  it("places every day of every month of 2025-2027 under the right weekday, in 5 or 6 rows", () => {
    for (let year = 2025; year <= 2027; year++) {
      for (let month = 1; month <= 12; month++) {
        const grid = buildMonthGrid(year, month);
        expect([5, 6]).toContain(grid.length);
        grid.forEach(row => expect(row).toHaveLength(7));
        expect(grid.flat().filter(cell => cell !== null)).toHaveLength(daysInMonth(year, month));
        expectEveryDayUnderItsWeekday(year, month);
      }
    }
  });
});

describe("isoDate", () => {
  it("zero-pads the month and day", () => {
    expect(isoDate(2026, 3, 7)).toBe("2026-03-07");
  });
});
