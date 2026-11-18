// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

import AttendanceStatusTabs from "./AttendanceStatusTabs";
import AttendanceSummaryStrip from "./AttendanceSummaryStrip";
import AttendanceTable from "./AttendanceTable";
import type { AttendanceRow } from "@/types/attendance";

afterEach(() => cleanup());

const row = (overrides: Partial<AttendanceRow> = {}): AttendanceRow => ({
  record_id: "r1", employee_id: "EMP001", name: "Asha Rao", initials: "AR", department: "Finance", branch: "Mulugu",
  clock_in: "09:05", clock_out: "18:10", total_hours: "9h 5m", ot: "40m", status: "Present", status_key: "present", is_late: false, ...overrides,
});
const CHIPS = { present: 3, late: 1, absent: 11, on_leave: 2, half_day: 0, weekly_off: 4, holiday: 0 };

describe("AttendanceTable", () => {
  const props = { loading: false, sort: { by: "name" as const, dir: "asc" as const }, onSortChange: vi.fn(), onOpen: vi.fn() };

  it("shows five columns, with clock in and out together and overtime beside the hours", () => {
    render(<AttendanceTable {...props} rows={[row()]} />);
    expect(screen.getAllByRole("columnheader").map(header => header.textContent?.trim())).toEqual(["Employee", "Department", "Time", "Hours", "Status", ""]);
    const cells = within(screen.getByRole("row", { name: "Open Asha Rao" }));
    expect(cells.getByText("09:05")).toBeTruthy();
    expect(cells.getByText("18:10")).toBeTruthy();
    expect(cells.getByText("9h 5m")).toBeTruthy();
    expect(cells.getByTitle("Overtime").textContent).toBe("+40m OT");
    expect(cells.getByText("Present")).toBeTruthy();
    expect(cells.getByText("Mulugu")).toBeTruthy();
  });

  it("says 'No punch' for an absent employee instead of rows of dashes", () => {
    render(<AttendanceTable {...props} rows={[row({ record_id: null, clock_in: "—", clock_out: "—", total_hours: "—", ot: "—", status: "Absent", status_key: "absent" })]} />);
    expect(screen.getByText("No punch")).toBeTruthy();
    expect(screen.queryByTitle("Overtime")).toBeNull();
  });

  it("shows 'still in' for someone who has clocked in but not out, and marks a late arrival", () => {
    render(<AttendanceTable {...props} rows={[row({ clock_out: "—", total_hours: "—", ot: "—", is_late: true, status: "Late", status_key: "late" })]} />);
    expect(screen.getByText("still in")).toBeTruthy();
    expect(screen.getByTitle("Arrived late")).toBeTruthy();
  });

  it("opens the row on click and on Enter", () => {
    const onOpen = vi.fn();
    const target = row();
    render(<AttendanceTable {...props} onOpen={onOpen} rows={[target]} />);
    const line = screen.getByRole("row", { name: "Open Asha Rao" });
    fireEvent.click(line);
    fireEvent.keyDown(line, { key: "Enter" });
    expect(onOpen).toHaveBeenCalledTimes(2);
    expect(onOpen).toHaveBeenCalledWith(target);
  });

  it("sorts by the clicked column and shows the current direction", () => {
    const onSortChange = vi.fn();
    render(<AttendanceTable {...props} onSortChange={onSortChange} rows={[row()]} />);
    fireEvent.click(screen.getByRole("button", { name: "Sort by Status" }));
    expect(onSortChange).toHaveBeenCalledWith({ by: "status", dir: "asc" });
    fireEvent.click(screen.getByRole("button", { name: "Sort by Employee" }));
    expect(onSortChange).toHaveBeenLastCalledWith({ by: "name", dir: "desc" });
    expect(screen.getByRole("columnheader", { name: /Employee/ }).getAttribute("aria-sort")).toBe("ascending");
  });

  it("shows Loading and the empty message", () => {
    const { rerender } = render(<AttendanceTable {...props} loading rows={[]} />);
    expect(screen.getByText("Loading…")).toBeTruthy();
    rerender(<AttendanceTable {...props} loading={false} rows={[]} />);
    expect(screen.getByText("No attendance records for this filter.")).toBeTruthy();
  });
});

describe("AttendanceStatusTabs", () => {
  const base = { status: "", onStatusChange: vi.fn(), chips: CHIPS, search: "", onSearchChange: vi.fn() };

  it("shows each status with its count, and All without one", () => {
    render(<AttendanceStatusTabs {...base} />);
    expect(screen.getByRole("button", { name: "All" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Absent\s*11/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Half Day\s*0/ })).toBeTruthy();
  });

  it("filters on click, and clicking the chosen status again clears it", () => {
    const onStatusChange = vi.fn();
    const { rerender } = render(<AttendanceStatusTabs {...base} onStatusChange={onStatusChange} />);
    fireEvent.click(screen.getByRole("button", { name: /Absent/ }));
    expect(onStatusChange).toHaveBeenCalledWith("absent");
    rerender(<AttendanceStatusTabs {...base} status="absent" onStatusChange={onStatusChange} />);
    expect(screen.getByRole("button", { name: /Absent/ }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: /Absent/ }));
    expect(onStatusChange).toHaveBeenLastCalledWith("");
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(onStatusChange).toHaveBeenLastCalledWith("");
  });

  it("passes what is typed in the search box", () => {
    const onSearchChange = vi.fn();
    render(<AttendanceStatusTabs {...base} onSearchChange={onSearchChange} />);
    fireEvent.change(screen.getByLabelText("Search employees"), { target: { value: "asha" } });
    expect(onSearchChange).toHaveBeenCalledWith("asha");
  });
});

describe("AttendanceSummaryStrip", () => {
  const cards = { present_today: 0, absent: 11, late_arrivals: 0, on_leave: 0, total_employees: 11 };

  it("shows today's four numbers and each one jumps to its rows", () => {
    const onJump = vi.fn();
    render(<AttendanceSummaryStrip cards={cards} onJump={onJump} />);
    const strip = within(screen.getByRole("group", { name: "Today at a glance" }));
    expect(strip.getByText("of 11 employees")).toBeTruthy();
    fireEvent.click(strip.getByRole("button", { name: /Absent/ }));
    fireEvent.click(strip.getByRole("button", { name: /On leave/ }));
    fireEvent.click(strip.getByRole("button", { name: /Late arrivals/ }));
    fireEvent.click(strip.getByRole("button", { name: /Present today/ }));
    expect(onJump.mock.calls.map(call => call[0])).toEqual(["absent", "on_leave", "late", "present"]);
  });

  it("shows a dash while the numbers load", () => {
    render(<AttendanceSummaryStrip cards={undefined} onJump={vi.fn()} />);
    expect(screen.getAllByText("—")).toHaveLength(4);
  });
});
