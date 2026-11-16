// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { WeeklyTimesheetSummary } from "@/types/timesheet";

let viewedEmployee: string | null = null;
vi.mock("@/lib/viewAs", () => ({ getViewAsEmployee: () => viewedEmployee }));
vi.mock("next/link", () => ({ default: ({ href, className, children }: { href: string; className?: string; children: React.ReactNode }) => <a href={href} className={className}>{children}</a> }));

import TimesheetCardAction from "./TimesheetCardAction";

const summary = (status: WeeklyTimesheetSummary["timesheet_status"] = null): WeeklyTimesheetSummary => ({
  hours_logged: 16, target_hours: 40, week_start: "2026-11-09", week_end: "2026-11-15", submitted: false, submitted_at: null, timesheet_status: status,
});

beforeEach(() => { viewedEmployee = null; });
afterEach(() => cleanup());

describe("TimesheetCardAction", () => {
  it("opens the timesheet in place when the parent can show it (a button, no navigation)", () => {
    const onOpen = vi.fn();
    render(<TimesheetCardAction summary={summary("draft")} className="rvbtn pri" onOpen={onOpen} />);
    expect(screen.queryByRole("link")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Continue timesheet" }));
    expect(onOpen).toHaveBeenCalledWith("2026-11-09");
  });

  it("is a link into the workspace's timesheet view when there is no parent to open it", () => {
    render(<TimesheetCardAction summary={summary()} className="btn" />);
    expect(screen.getByRole("link", { name: "Fill timesheet" }).getAttribute("href")).toBe("/dashboard/ess?tab=timesheet&week=2026-11-09");
  });

  it("is hidden in both forms while an admin views someone else's workspace", () => {
    viewedEmployee = "someone-else";
    const { container, rerender } = render(<TimesheetCardAction summary={summary()} className="btn" onOpen={vi.fn()} />);
    expect(container.innerHTML).toBe("");
    rerender(<TimesheetCardAction summary={summary()} className="btn" />);
    expect(container.innerHTML).toBe("");
  });
});
