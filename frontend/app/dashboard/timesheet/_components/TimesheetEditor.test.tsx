// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DATES, internalLine, line, weekView } from "@/components/timesheet/fixtures";
import type { TimesheetWeekView } from "@/types/timesheet";
import TimesheetEditor from "./TimesheetEditor";

afterEach(() => cleanup());

function mount(view: TimesheetWeekView, over: { problems?: string[]; onSave?: () => Promise<boolean>; onSubmit?: () => Promise<boolean> } = {}) {
  const onSave = vi.fn(over.onSave ?? (async () => true));
  const onSubmit = vi.fn(over.onSubmit ?? (async () => true));
  render(<TimesheetEditor view={view} isSaving={false} isSubmitting={false} problems={over.problems ?? []} onSave={onSave} onSubmit={onSubmit} />);
  return { onSave, onSubmit };
}

// Project cards start closed: open the one a field belongs to (if it is not open yet), then type into the field.
const openFor = (label: string) => {
  const project = label.split(/ (?:hours|note) on /)[0];
  if (!screen.queryByLabelText(label)) fireEvent.click(screen.getByRole("button", { name: `Edit hours for ${project}` }));
};
const type = (label: string, value: string) => { openFor(label); fireEvent.change(screen.getByLabelText(label), { target: { value } }); };
const alpha = (index: number) => `Alpha hours on ${DATES[index]}`;

describe("TimesheetEditor: a draft", () => {
  it("starts with Save disabled (nothing changed) and Submit available", () => {
    mount(weekView());
    expect((screen.getByRole("button", { name: "Save draft" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Submit for approval" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("updates totals live as hours are typed, with billable split", () => {
    mount(weekView());
    type(alpha(0), "8");
    fireEvent.click(screen.getByLabelText("Alpha is billable"));
    type("Internal / Non-project work hours on 2026-11-09", "1.5");
    expect(screen.getByTestId("week-total").textContent).toBe("9.5");
    const summary = screen.getByText(/Week total/).textContent ?? "";
    expect(summary).toContain("9.5");
    expect(summary).toContain("of 40 target hours");
    expect(summary).toContain("Billable 8");
    expect(summary).toContain("Non-billable 1.5");
  });

  it("saves exactly what was typed (quarter hours, notes, billable) and nothing for empty cells", async () => {
    const { onSave } = mount(weekView());
    type(alpha(0), "7.5");
    fireEvent.click(screen.getByLabelText("Alpha is billable"));
    type("Alpha note on 2026-11-09", " api ");
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(onSave).toHaveBeenCalledWith({
      lines: [
        { assignment_id: 1, is_internal: false, is_billable: true, entries: [{ date: "2026-11-09", hours: "7.50", note: "api" }] },
        { assignment_id: null, is_internal: true, is_billable: false, entries: [] },
      ],
    });
  });

  it("blocks Save and Submit while an hour is not a quarter-hour number, and explains", () => {
    mount(weekView());
    type(alpha(0), "7.3");
    expect(screen.getByRole("alert").textContent).toContain("quarter hours");
    expect((screen.getByRole("button", { name: "Save draft" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Submit for approval" }) as HTMLButtonElement).disabled).toBe(true);
    type(alpha(0), "7.25");
    expect(screen.queryByText(/not valid/)).toBeNull();
    expect((screen.getByRole("button", { name: "Submit for approval" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("saves first when there are unsaved changes, then submits", async () => {
    const order: string[] = [];
    const { onSave, onSubmit } = mount(weekView(), {
      onSave: async () => { order.push("save"); return true; }, onSubmit: async () => { order.push("submit"); return true; },
    });
    type(alpha(0), "8");
    fireEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(order).toEqual(["save", "submit"]);
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("does not submit when the save it needed failed", async () => {
    const { onSave, onSubmit } = mount(weekView(), { onSave: async () => false });
    type(alpha(0), "8");
    fireEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits straight away when nothing changed since the last save", async () => {
    const saved = weekView({ lines: [line({ entries: { [DATES[0]]: { hours: "8.00", note: "" } } }), internalLine()] });
    const { onSave, onSubmit } = mount(saved);
    fireEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSave).not.toHaveBeenCalled();
  });

  it("lists every problem the server gave, and shows its warnings", () => {
    mount(weekView({ issues: { errors: [], warnings: [{ code: "long_day", date: DATES[0], message: "Mon 9 Nov: 13.00 hours in one day." }] } }), { problems: ["Mon 9 Nov: not assigned.", "Thu 12 Nov: not happened."] });
    expect(screen.getByRole("alert").textContent).toContain("Mon 9 Nov: not assigned.");
    expect(screen.getByRole("alert").textContent).toContain("Thu 12 Nov: not happened.");
    expect(screen.getByText("Mon 9 Nov: 13.00 hours in one day.")).toBeTruthy();
  });
});

describe("TimesheetEditor: other states", () => {
  it("a returned sheet shows the reason, is editable and says Resubmit", () => {
    mount(weekView({ status: "returned", return_reason: "Wrong project on Monday" }));
    expect(screen.getByText(/Wrong project on Monday/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Resubmit" })).toBeTruthy();
    openFor(alpha(0));
    expect((screen.getByLabelText(alpha(0)) as HTMLInputElement).disabled).toBe(false);
  });

  it.each([
    ["submitted", { approver: { id: "M", name: "Priya Nair", employee_id: "M1" } }, /Waiting for approval from Priya Nair/],
    ["approved", { decided_by: { id: "M", name: "Priya Nair", employee_id: "M1" } }, /Approved by Priya Nair. This timesheet is locked/],
  ] as const)("a %s sheet is read-only with no Save or Submit", (status, extra, banner) => {
    mount(weekView({ status, is_editable: false, ...extra }));
    expect(screen.getByText(banner)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Submit|Resubmit/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Edit hours/ })).toBeNull();                  // only "View days" is offered
    fireEvent.click(screen.getByRole("button", { name: "View days for Alpha" }));
    for (const input of screen.getAllByRole("textbox")) expect((input as HTMLInputElement).disabled).toBe(true);
  });

  it("shows the history", () => {
    mount(weekView({ status: "returned", return_reason: "x", events: [
      { id: "e1", event_type: "submitted", from_status: "draft", to_status: "submitted", reason: "", actor: { id: "U1", name: "Asha Rao", employee_id: "E001" }, at: "2026-11-10T10:00:00Z" },
      { id: "e2", event_type: "returned", from_status: "submitted", to_status: "returned", reason: "Wrong project", actor: { id: "M", name: "Priya Nair", employee_id: "M1" }, at: "2026-11-11T10:00:00Z" },
    ] }));
    const history = screen.getByRole("list", { name: "Timesheet history" });
    expect(history.textContent).toContain("Submitted by Asha Rao");
    expect(history.textContent).toContain("Sent back by Priya Nair");
    expect(history.textContent).toContain("Wrong project");
  });
});
