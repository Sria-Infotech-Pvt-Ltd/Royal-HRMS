// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { toGridLines } from "@/lib/timesheet";
import type { TimesheetDay, TimesheetLine } from "@/types/timesheet";
import { DATES, day, internalLine, line, weekView } from "./fixtures";
import TimesheetProjects from "./TimesheetProjects";

afterEach(() => cleanup());

function mount(over: { isReadOnly?: boolean; days?: TimesheetDay[]; lines?: TimesheetLine[] } = {}) {
  const handlers = { onHoursChange: vi.fn(), onNoteChange: vi.fn(), onBillableChange: vi.fn() };
  const view = weekView();
  render(
    <TimesheetProjects
      days={over.days ?? view.days} lines={toGridLines(over.lines ?? view.lines)} limits={view.limits}
      isReadOnly={over.isReadOnly ?? false} {...handlers}
    />,
  );
  return handlers;
}

const open = (project: string) => fireEvent.click(screen.getByRole("button", { name: new RegExp(`^(Edit hours for|View days for) ${project}$`) }));

describe("TimesheetProjects: the cards", () => {
  it("shows one card per project and one for Internal work, each with its hours for the week", () => {
    mount({ lines: [line({ entries: { [DATES[0]]: { hours: "8", note: "" }, [DATES[1]]: { hours: "7.5", note: "" } } }), internalLine({ entries: { [DATES[0]]: { hours: "1", note: "" } } })] });
    expect(screen.getByRole("region", { name: "Alpha" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Internal / Non-project work" })).toBeTruthy();
    expect(screen.getByLabelText("Alpha total hours").textContent).toBe("15.5 h");
    expect(screen.getByLabelText("Internal / Non-project work total hours").textContent).toBe("1 h");
  });

  it("a closed card lists the days that have hours, or says there are none", () => {
    mount({ lines: [line({ entries: { [DATES[0]]: { hours: "8", note: "" } } }), internalLine()] });
    const alpha = screen.getByRole("region", { name: "Alpha" });
    expect(within(alpha).getByText("Mon 8")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Internal / Non-project work" })).getByText("No hours yet this week.")).toBeTruthy();
  });

  it("opens to the seven days with an hours box and a note box each, and closes again", () => {
    mount();
    expect(screen.queryByLabelText(`Alpha hours on ${DATES[0]}`)).toBeNull();
    open("Alpha");
    for (const date of DATES) {
      expect(screen.getByLabelText(`Alpha hours on ${date}`)).toBeTruthy();
      expect(screen.getByLabelText(`Alpha note on ${date}`)).toBeTruthy();
    }
    fireEvent.click(screen.getByRole("button", { name: "Close Alpha" }));
    expect(screen.queryByLabelText(`Alpha hours on ${DATES[0]}`)).toBeNull();
  });

  it("reports what is typed for the right project and day, and the note, and the billable toggle", () => {
    const { onHoursChange, onNoteChange, onBillableChange } = mount();
    open("Alpha");
    fireEvent.change(screen.getByLabelText("Alpha hours on 2026-11-10"), { target: { value: "7.5" } });
    fireEvent.change(screen.getByLabelText("Alpha note on 2026-11-10"), { target: { value: "api work" } });
    fireEvent.click(screen.getByLabelText("Alpha is billable"));
    expect(onHoursChange).toHaveBeenCalledWith("L1", "2026-11-10", "7.5");
    expect(onNoteChange).toHaveBeenCalledWith("L1", "2026-11-10", "api work");
    expect(onBillableChange).toHaveBeenCalledWith("L1", true);
  });

  it("flags an invalid hours box", () => {
    mount({ lines: [line({ entries: { [DATES[0]]: { hours: "7.3", note: "" } } })] });
    open("Alpha");
    expect(screen.getByLabelText(`Alpha hours on ${DATES[0]}`).getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByLabelText(`Alpha hours on ${DATES[1]}`).getAttribute("aria-invalid")).toBe("false");
  });

  it("keeps holiday, weekly-off and leave days typeable, and closes not-employed and future days", () => {
    mount({
      days: [
        day(0, { status: "holiday", holiday_name: "Diwali" }), day(1, { status: "on_leave" }), day(2, { status: "weekly_off" }),
        day(3, { status: "not_employed", is_employed: false }), day(4, { is_future: true }), day(5), day(6),
      ],
    });
    open("Alpha");
    for (const index of [0, 1, 2, 5]) expect((screen.getByLabelText(`Alpha hours on ${DATES[index]}`) as HTMLInputElement).disabled).toBe(false);
    for (const index of [3, 4]) expect((screen.getByLabelText(`Alpha hours on ${DATES[index]}`) as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText(`Alpha note on ${DATES[3]}`) as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText(`Alpha note on ${DATES[4]}`) as HTMLInputElement).disabled).toBe(false);
  });
});

describe("TimesheetProjects: read-only", () => {
  it("offers 'View days' not 'Edit hours', and every box and the billable toggle is disabled", () => {
    mount({ isReadOnly: true, lines: [line({ entries: { [DATES[0]]: { hours: "8", note: "api" } } })] });
    expect(screen.queryByRole("button", { name: /Edit hours/ })).toBeNull();
    open("Alpha");
    for (const input of screen.getAllByRole("textbox")) expect((input as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText("Alpha is billable") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText(`Alpha hours on ${DATES[0]}`) as HTMLInputElement).value).toBe("8");
    expect((screen.getByLabelText(`Alpha note on ${DATES[0]}`) as HTMLInputElement).value).toBe("api");
  });
});

describe("TimesheetProjects: the day strip", () => {
  it("adds hours across projects per day and for the week", () => {
    mount({ lines: [line({ entries: { [DATES[0]]: { hours: "8", note: "" }, [DATES[1]]: { hours: "4.5", note: "" } } }), internalLine({ entries: { [DATES[0]]: { hours: "1.5", note: "" } } })] });
    expect(screen.getByTestId(`day-total-${DATES[0]}`).textContent).toBe("9.5");
    expect(screen.getByTestId(`day-total-${DATES[1]}`).textContent).toBe("4.5");
    expect(screen.getByTestId("week-total").textContent).toBe("14");
  });

  it("marks a day over 12 hours amber and over 24 hours red", () => {
    mount({ lines: [line({ entries: { [DATES[0]]: { hours: "13", note: "" }, [DATES[1]]: { hours: "14", note: "" } } }), internalLine({ entries: { [DATES[1]]: { hours: "12", note: "" } } })] });
    expect(screen.getByTestId(`day-total-${DATES[0]}`).getAttribute("style")).toContain("var(--warn)");
    expect(screen.getByTestId(`day-total-${DATES[1]}`).getAttribute("style")).toContain("var(--crit)");
  });

  it("chips the non-working days and shows attendance hours apart from project hours", () => {
    mount({
      days: [
        day(0, { status: "holiday", holiday_name: "Diwali", attendance_minutes: 450 }), day(1, { status: "on_leave" }), day(2, { status: "weekly_off" }),
        day(3, { status: "not_employed", is_employed: false }), day(4), day(5), day(6),
      ],
    });
    for (const chip of ["Diwali", "On leave", "Weekly off", "Not employed"]) expect(screen.getAllByText(chip).length).toBeGreaterThan(0);
    expect(screen.getByText("7.5 h punched")).toBeTruthy();
    expect(screen.getAllByText("no punches").length).toBe(6);
  });
});
