// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { weekView } from "@/components/timesheet/fixtures";
import type { TimesheetWeekView } from "@/types/timesheet";

const refetch = vi.fn();
let hookState: { view: TimesheetWeekView | null; loading: boolean; error: string | null };
const requestedWeeks: string[] = [];

vi.mock("@/hooks/useTimesheetWeek", () => ({
  useTimesheetWeek: (week: string) => {
    requestedWeeks.push(week);
    return { ...hookState, refetch, save: vi.fn(), submit: vi.fn(), isSaving: false, isSubmitting: false, problems: [], clearProblems: vi.fn() };
  },
}));

import EssTimesheetTab from "./EssTimesheetTab";

const mount = (over: { week?: string; isReadOnly?: boolean } = {}) => {
  const onGoToWeek = vi.fn();
  const onBack = vi.fn();
  render(<EssTimesheetTab week={over.week ?? "2026-11-09"} isReadOnly={over.isReadOnly ?? false} onGoToWeek={onGoToWeek} onBack={onBack} />);
  return { onGoToWeek, onBack };
};

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 14, 10, 0));          // Saturday 14 Nov 2026: this week's Monday is 9 Nov
  requestedWeeks.length = 0; refetch.mockReset();
  hookState = { view: weekView(), loading: false, error: null };
});
afterEach(() => { vi.useRealTimers(); cleanup(); });

describe("My Workspace > Weekly timesheet", () => {
  it("shows the week, its status, the due date and the project cards", () => {
    mount();
    expect(requestedWeeks[0]).toBe("2026-11-09");
    expect(screen.getByText("9 – 15 Nov 2026")).toBeTruthy();
    expect(screen.getAllByText("Draft").length).toBeGreaterThan(0);
    expect(screen.getByRole("region", { name: "Alpha" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Submit for approval" })).toBeTruthy();
  });

  it("goes back to the Attendance tab", () => {
    const { onBack } = mount();
    fireEvent.click(screen.getByRole("button", { name: /Back to Attendance/ }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("moves between weeks by asking the workspace to change the week", () => {
    const { onGoToWeek } = mount();
    fireEvent.click(screen.getByRole("button", { name: "Previous week" }));
    expect(onGoToWeek).toHaveBeenCalledWith("2026-11-02");
  });

  it("cannot go past this week; an earlier week can go forward and jump back to this week", () => {
    mount();
    expect((screen.getByRole("button", { name: "Next week" }) as HTMLButtonElement).disabled).toBe(true);
    cleanup();
    hookState = { view: weekView({ week_start: "2026-11-02", week_end: "2026-11-08" }), loading: false, error: null };
    const { onGoToWeek } = mount({ week: "2026-11-02" });
    fireEvent.click(screen.getByRole("button", { name: "Next week" }));
    fireEvent.click(screen.getByRole("button", { name: "This week" }));
    expect(onGoToWeek).toHaveBeenNthCalledWith(1, "2026-11-09");
    expect(onGoToWeek).toHaveBeenNthCalledWith(2, "2026-11-09");
  });

  it("is view-only while an admin looks at someone else's workspace", () => {
    mount({ isReadOnly: true });
    expect(screen.queryByRole("button", { name: /Save draft|Submit/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Edit hours/ })).toBeNull();
    expect(screen.getAllByRole("button", { name: /View days for/ }).length).toBeGreaterThan(0);
  });

  it("shows loading, then a retry when the sheet cannot be loaded", () => {
    hookState = { view: null, loading: true, error: null };
    const { unmount } = render(<EssTimesheetTab week="2026-11-09" isReadOnly={false} onGoToWeek={vi.fn()} onBack={vi.fn()} />);
    expect(screen.getByText("Loading…")).toBeTruthy();
    unmount();
    hookState = { view: null, loading: false, error: "Request failed." };
    render(<EssTimesheetTab week="2026-11-09" isReadOnly={false} onGoToWeek={vi.fn()} onBack={vi.fn()} />);
    expect(screen.getByRole("alert").textContent).toContain("Request failed.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(refetch).toHaveBeenCalled();
  });
});
