// Month-grid maths for the attendance calendar: Sunday-first weeks, blank
// cells before the 1st and after the last day, and a fixed minimum row count
// so the calendar keeps the same height from month to month.

/** Column headings, Sunday first (matches Date.getDay(): 0 = Sunday). */
export const WEEKDAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

/** Every month is shown with at least this many weeks (a 28-day February starting on Sunday fills only 4). */
export const MIN_CALENDAR_ROWS = 5;

/** A grid cell: the day of the month, or null for a blank cell outside the month. */
export type CalendarCell = number | null;

export function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

/** Weekday of the 1st of the month: 0 = Sunday … 6 = Saturday. `month` is 1-12. */
export function firstWeekday(year: number, month: number): number {
  return new Date(year, month - 1, 1).getDay();
}

/** Weeks of the month as rows of seven cells, Sunday first. `month` is 1-12. */
export function buildMonthGrid(year: number, month: number, minRows: number = MIN_CALENDAR_ROWS): CalendarCell[][] {
  const leadingBlanks = firstWeekday(year, month);
  const totalDays = daysInMonth(year, month);
  const rowCount = Math.max(minRows, Math.ceil((leadingBlanks + totalDays) / 7));
  return Array.from({ length: rowCount }, (_, row) =>
    Array.from({ length: 7 }, (_, column) => {
      const day = row * 7 + column - leadingBlanks + 1;
      return day >= 1 && day <= totalDays ? day : null;
    }),
  );
}

/** ISO date (YYYY-MM-DD) for a day of the month. `month` is 1-12. */
export function isoDate(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}
