// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { WeeklyTimesheetSummary } from "@/types/timesheet";

let summary: WeeklyTimesheetSummary | null = null;
let viewedEmployee: string | null = null;
vi.mock("@/hooks/useWeeklyTimesheet", () => ({ useWeeklyTimesheet: () => ({ data: summary, loading: false, refetch: vi.fn() }) }));
vi.mock("@/lib/viewAs", () => ({ getViewAsEmployee: () => viewedEmployee }));
vi.mock("next/link", () => ({ default: ({ href, className, children }: { href: string; className?: string; children: React.ReactNode }) => <a href={href} className={className}>{children}</a> }));

import WeeklyTimesheetCard from "./WeeklyTimesheetCard";

const base: WeeklyTimesheetSummary = {
  hours_logged: 16, target_hours: 40, week_start: "2026-11-09", week_end: "2026-11-15", submitted: false, submitted_at: null, timesheet_status: null,
};

beforeEach(() => { summary = base; viewedEmployee = null; });
afterEach(() => cleanup());

describe("WeeklyTimesheetCard", () => {
  it("renders nothing until the summary arrives", () => {
    summary = null;
    const { container } = render(<WeeklyTimesheetCard />);
    expect(container.innerHTML).toBe("");
  });

  it.each([
    [null, "Fill timesheet", "DUE FRI"],
    ["draft", "Continue timesheet", "DUE FRI"],
    ["returned", "Fix and resubmit", "RETURNED"],
    ["submitted", "View timesheet", "SUBMITTED"],
    ["approved", "View timesheet", "APPROVED"],
  ] as const)("when the sheet is %j the button says %j and the badge %j", (status, button, badge) => {
    summary = { ...base, timesheet_status: status };
    render(<WeeklyTimesheetCard />);
    const link = screen.getByRole("link", { name: button });
    expect(link.getAttribute("href")).toBe("/dashboard/ess?tab=timesheet&week=2026-11-09");
    expect(screen.getByText(badge)).toBeTruthy();
  });

  it("no longer submits from the card: there is no Submit timesheet button", () => {
    render(<WeeklyTimesheetCard />);
    expect(screen.queryByRole("button", { name: /Submit timesheet/ })).toBeNull();
  });

  it("an old tick-box submission still reads as submitted", () => {
    summary = { ...base, submitted: true, timesheet_status: null };
    render(<WeeklyTimesheetCard />);
    expect(screen.getByText("SUBMITTED")).toBeTruthy();
  });

  it("the compact Home row shows the badge but no button", () => {
    summary = { ...base, timesheet_status: "returned" };
    render(<WeeklyTimesheetCard compact />);
    expect(screen.getByText("RETURNED")).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("hides the button while an admin views someone else's workspace", () => {
    viewedEmployee = "uuid-of-someone-else";
    render(<WeeklyTimesheetCard />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("Weekly timesheet")).toBeTruthy();
  });

  it("says how many hours are left before the target, with correct singular and plural", () => {
    summary = { ...base, hours_logged: 39 };
    const { unmount } = render(<WeeklyTimesheetCard />);
    expect(screen.getByText(/1 hour remaining/)).toBeTruthy();
    unmount();
    summary = { ...base, hours_logged: 40 };
    render(<WeeklyTimesheetCard />);
    expect(screen.getByText(/Target reached/)).toBeTruthy();
  });
});
