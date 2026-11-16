import { describe, expect, it } from "vitest";
import type { GridLine, TimesheetDay, TimesheetLine, WeeklyTimesheetSummary } from "@/types/timesheet";
import {
  addDays, billableTotal, cardActionLabel, cellHours, currentMonday, dailyTotals, dayChipLabel, dueDayLabel, formatHours, hasInvalidCells,
  isDirty, isIsoDate, mondayOf, parseHoursText, problemsFromError, timesheetCardState, toGridLines, toSavePayload, weekRangeLabel, weekTotal,
} from "./timesheet";

const DATES = ["2026-11-09", "2026-11-10", "2026-11-11"];

const line = (over: Partial<GridLine> = {}): GridLine => ({
  key: "a", assignment_id: 1, project_name: "Alpha", project_code: "P1", is_internal: false, is_billable: false, cells: {}, ...over,
});

describe("parseHoursText", () => {
  it.each([["", 0], ["0", 0], ["8", 8], ["7.5", 7.5], ["7.25", 7.25], ["7.75", 7.75], ["24", 24], ["0.25", 0.25], ["8.00", 8], [" 3 ", 3]])(
    "%j is %j hours", (text, expected) => expect(parseHoursText(text)).toBe(expected),
  );
  it.each(["0.1", "7.3", "24.25", "25", "-1", "abc", "1,5", "1e1", "1.234", ".5", "8h", "99"])(
    "%j is not a valid number of hours", text => expect(parseHoursText(text)).toBeNull(),
  );
  it("counts an invalid cell as 0 in totals", () => expect(cellHours("7.3")).toBe(0));
  it("formats without trailing zeros", () => expect([formatHours(8), formatHours(7.5), formatHours(7.25), formatHours(0)]).toEqual(["8", "7.5", "7.25", "0"]));
});

describe("totals", () => {
  const lines = [
    line({ cells: { "2026-11-09": { hours: "8", note: "" }, "2026-11-10": { hours: "4.5", note: "" } }, is_billable: true }),
    line({ key: "b", assignment_id: null, is_internal: true, cells: { "2026-11-09": { hours: "1", note: "" }, "2026-11-11": { hours: "7.3", note: "" } } }),
  ];
  it("adds per day, per week and billable", () => {
    expect(dailyTotals(lines, DATES)).toEqual({ "2026-11-09": 9, "2026-11-10": 4.5, "2026-11-11": 0 });
    expect(weekTotal(lines, DATES)).toBe(13.5);
    expect(billableTotal(lines, DATES)).toBe(12.5);
  });
  it("sees an invalid cell", () => {
    expect(hasInvalidCells(lines)).toBe(true);
    expect(hasInvalidCells([lines[0]])).toBe(false);
  });
});

describe("save payload", () => {
  it("sends only cells with hours or a note, as 2-decimal text, in date order, and trims notes", () => {
    const payload = toSavePayload([line({
      is_billable: true,
      cells: {
        "2026-11-11": { hours: "2", note: "" }, "2026-11-09": { hours: "7.5", note: "  api  " },
        "2026-11-10": { hours: "", note: "" }, "2026-11-12": { hours: "0", note: "off sick" },
      },
    })]);
    expect(payload.lines[0].entries).toEqual([
      { date: "2026-11-09", hours: "7.50", note: "api" },
      { date: "2026-11-11", hours: "2.00", note: "" },
      { date: "2026-11-12", hours: "0.00", note: "off sick" },
    ]);
    expect(payload.lines[0]).toMatchObject({ assignment_id: 1, is_internal: false, is_billable: true });
  });
  it("sends the Internal row with no assignment", () => {
    expect(toSavePayload([line({ assignment_id: null, is_internal: true })]).lines[0]).toMatchObject({ assignment_id: null, is_internal: true });
  });
  it("round-trips the server's lines (0.00 becomes an empty cell)", () => {
    const server: TimesheetLine[] = [{
      id: "L1", assignment_id: 1, project_id: 10, project_code: "P1", project_name: "Alpha", is_internal: false, is_billable: true,
      entries: { "2026-11-09": { hours: "8.00", note: "x" }, "2026-11-10": { hours: "0.00", note: "n" } },
    }];
    const grid = toGridLines(server);
    expect(grid[0].cells).toEqual({ "2026-11-09": { hours: "8", note: "x" }, "2026-11-10": { hours: "", note: "n" } });
    expect(isDirty(grid, toGridLines(server))).toBe(false);
  });
  it("is dirty after an edit, and not after typing then clearing a cell", () => {
    const saved = [line({ cells: { "2026-11-09": { hours: "8", note: "" } } })];
    expect(isDirty([line({ cells: { "2026-11-09": { hours: "7", note: "" } } })], saved)).toBe(true);
    expect(isDirty([line({ cells: { "2026-11-09": { hours: "8", note: "" }, "2026-11-10": { hours: "", note: "" } } })], saved)).toBe(false);
  });
});

describe("week dates", () => {
  it("finds the Monday of any day, including a Sunday and a month boundary", () => {
    expect([mondayOf("2026-11-09"), mondayOf("2026-11-15"), mondayOf("2026-11-11"), mondayOf("2026-12-01")]).toEqual(["2026-11-09", "2026-11-09", "2026-11-09", "2026-11-30"]);
  });
  it("adds days across months and years", () => {
    expect([addDays("2026-11-30", 1), addDays("2026-12-31", 1), addDays("2026-11-09", -7)]).toEqual(["2026-12-01", "2027-01-01", "2026-11-02"]);
  });
  it("uses the local calendar day for 'this week'", () => expect(currentMonday(new Date(2026, 10, 14, 23, 59))).toBe("2026-11-09"));
  it("labels a week, with the month once or twice", () => {
    expect(weekRangeLabel("2026-11-09", "2026-11-15")).toBe("9 – 15 Nov 2026");
    expect(weekRangeLabel("2026-11-30", "2026-12-06")).toBe("30 Nov – 6 Dec 2026");
  });
  it("recognises real dates only", () => {
    expect([isIsoDate("2026-11-09"), isIsoDate("2026-13-45"), isIsoDate("nonsense"), isIsoDate(null)]).toEqual([true, false, false, false]);
  });
});

describe("wording", () => {
  it.each([[null, "Fill timesheet"], ["draft", "Continue timesheet"], ["returned", "Fix and resubmit"], ["submitted", "View timesheet"], ["approved", "View timesheet"]] as const)(
    "the card button for %j is %j", (status, label) => expect(cardActionLabel(status)).toBe(label),
  );
  it("chips only the non-working days", () => {
    const day = (status: TimesheetDay["status"], holiday_name = ""): TimesheetDay =>
      ({ date: "2026-11-09", weekday: "Mon", status, status_label: "", holiday_name, is_future: false, is_employed: true, attendance_minutes: 0 });
    expect(dayChipLabel(day("holiday", "Diwali"))).toBe("Diwali");
    expect(dayChipLabel(day("holiday"))).toBe("Holiday");
    expect([dayChipLabel(day("weekly_off")), dayChipLabel(day("on_leave")), dayChipLabel(day("not_employed")), dayChipLabel(day("present"))])
      .toEqual(["Weekly off", "On leave", "Not employed", null]);
  });
});

describe("the Home and Attendance card wording", () => {
  const summary = (over: Partial<WeeklyTimesheetSummary> = {}): WeeklyTimesheetSummary => ({
    hours_logged: 16, target_hours: 40, week_start: "2026-11-09", week_end: "2026-11-15", submitted: false, submitted_at: null, timesheet_status: null, ...over,
  });
  it("names the due weekday from the week's Monday", () => expect(dueDayLabel("2026-11-09")).toBe("FRI"));
  it.each([
    ["approved", "APPROVED", "badge-success", true], ["submitted", "SUBMITTED", "badge-success", true], ["returned", "RETURNED", "badge-error", false],
    ["draft", "DUE FRI", "badge-warn", false], [null, "DUE FRI", "badge-warn", false],
  ] as const)("a %j sheet shows %j", (status, badge, badgeClass, isDone) => {
    expect(timesheetCardState(summary({ timesheet_status: status }), "FRI")).toMatchObject({ badge, badgeClass, isDone });
  });
  it("still honours the old tick-box when there is no real timesheet", () => {
    expect(timesheetCardState(summary({ submitted: true }), "FRI")).toMatchObject({ badge: "SUBMITTED", isDone: true });
  });
  it("counts the hours left with the right plural, and says when the target is reached", () => {
    expect(timesheetCardState(summary({ hours_logged: 39 }), "FRI").subtitle).toContain("1 hour remaining");
    expect(timesheetCardState(summary({ hours_logged: 30 }), "FRI").subtitle).toContain("10 hours remaining");
    expect(timesheetCardState(summary({ hours_logged: 41 }), "FRI").subtitle).toContain("Target reached");
  });
});

describe("problemsFromError", () => {
  const apiError = (data: unknown) => ({ response: { data } });
  it("lists every server problem", () => {
    expect(problemsFromError(apiError({ message: "Some hours need fixing.", data: { errors: ["a", "b"] } }), "x")).toEqual(["a", "b"]);
  });
  it("falls back to the message, then to the fallback", () => {
    expect(problemsFromError(apiError({ message: "Not found", data: {} }), "x")).toEqual(["Not found"]);
    expect(problemsFromError(new Error("network"), "Could not save.")).toEqual(["Could not save."]);
    expect(problemsFromError(null, "Could not save.")).toEqual(["Could not save."]);
  });
});
