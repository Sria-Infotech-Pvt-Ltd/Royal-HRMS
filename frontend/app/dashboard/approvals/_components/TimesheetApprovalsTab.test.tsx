// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { TimesheetRow, TimesheetTeamPage } from "@/types/timesheet";

const refetch = vi.fn();
const calls: { filter: string; page: number }[] = [];
let queue: { page: TimesheetTeamPage | null; loading: boolean; error: string | null };

vi.mock("@/hooks/useTimesheetQueue", () => ({
  useTimesheetQueue: (filter: string, page: number) => { calls.push({ filter, page }); return { ...queue, refetch }; },
}));
vi.mock("./TimesheetDetailDrawer", () => ({
  default: ({ timesheetId, onChanged }: { timesheetId: string | null; onChanged: () => void }) => (
    <div data-testid="drawer" data-open={timesheetId ?? ""}><button onClick={onChanged}>stub-changed</button></div>
  ),
}));

import TimesheetApprovalsTab from "./TimesheetApprovalsTab";

const row = (over: Partial<TimesheetRow> = {}): TimesheetRow => ({
  id: "T1", employee: { id: "U1", name: "Asha Rao", employee_id: "E001" }, week_start: "2026-11-09", week_end: "2026-11-15", status: "submitted",
  is_late: false, total_hours: "38.50", billable_hours: "30.00", attendance_hours: "40.00", submitted_at: "2026-11-13T10:00:00Z", decided_at: null,
  approver: "Priya Nair", return_reason: "", can_decide: true, ...over,
});

const pageOf = (results: TimesheetRow[], over: Partial<TimesheetTeamPage> = {}): TimesheetTeamPage =>
  ({ count: results.length, page: 1, page_size: 20, total_pages: 1, results, pending_count: results.length, ...over });

beforeEach(() => { calls.length = 0; refetch.mockReset(); queue = { page: pageOf([row()]), loading: false, error: null }; });
afterEach(() => cleanup());

describe("Approvals > Timesheets", () => {
  it("opens on what is waiting for me and lists employee, week and the three kinds of hours", () => {
    render(<TimesheetApprovalsTab />);
    expect(calls[0]).toEqual({ filter: "submitted", page: 1 });
    const table = screen.getByRole("table", { name: "Timesheets" });
    for (const text of ["Asha Rao", "E001", "9 – 15 Nov 2026", "38.50", "30.00", "40.00", "13 Nov", "Submitted"]) expect(within(table).getAllByText(text).length).toBeGreaterThan(0);
  });

  it("shows how many are waiting on the filter button", () => {
    queue = { page: pageOf([row()], { pending_count: 7 }), loading: false, error: null };
    render(<TimesheetApprovalsTab />);
    expect(screen.getByRole("button", { name: "Waiting for me (7)" })).toBeTruthy();
  });

  it("flags a late submission", () => {
    queue = { page: pageOf([row({ is_late: true })]), loading: false, error: null };
    render(<TimesheetApprovalsTab />);
    expect(screen.getByText("Late")).toBeTruthy();
  });

  it("switches the filter, asking the server for that status from page 1", () => {
    render(<TimesheetApprovalsTab />);
    fireEvent.click(screen.getByRole("button", { name: "Approved" }));
    expect(calls.at(-1)).toEqual({ filter: "approved", page: 1 });
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(calls.at(-1)).toEqual({ filter: "all", page: 1 });
    expect(screen.getByRole("button", { name: "All" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("pages through a long list and goes back to page 1 when the filter changes", () => {
    queue = { page: pageOf([row()], { total_pages: 3, count: 45 }), loading: false, error: null };
    render(<TimesheetApprovalsTab />);
    expect((screen.getByRole("button", { name: "Previous" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(calls.at(-1)).toEqual({ filter: "submitted", page: 2 });
    fireEvent.click(screen.getByRole("button", { name: "Sent back" }));
    expect(calls.at(-1)).toEqual({ filter: "returned", page: 1 });
  });

  it("has no paging controls for a single page", () => {
    render(<TimesheetApprovalsTab />);
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
  });

  it("opens the drawer for the row that was reviewed", () => {
    render(<TimesheetApprovalsTab />);
    expect(screen.getByTestId("drawer").getAttribute("data-open")).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Review" }));
    expect(screen.getByTestId("drawer").getAttribute("data-open")).toBe("T1");
  });

  it("refreshes the list when a decision is made in the drawer", () => {
    render(<TimesheetApprovalsTab />);
    fireEvent.click(screen.getByText("stub-changed"));
    expect(refetch).toHaveBeenCalled();
  });

  it("says plainly when nothing is waiting, when there is nothing to show, while loading, and on an error", () => {
    queue = { page: pageOf([]), loading: false, error: null };
    const { unmount } = render(<TimesheetApprovalsTab />);
    expect(screen.getByText("No timesheets are waiting for you.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getByText("No timesheets to show.")).toBeTruthy();
    unmount();
    queue = { page: null, loading: true, error: null };
    const loading = render(<TimesheetApprovalsTab />);
    expect(screen.getByText("Loading…")).toBeTruthy();
    loading.unmount();
    queue = { page: null, loading: false, error: "Request failed." };
    render(<TimesheetApprovalsTab />);
    expect(screen.getByRole("alert").textContent).toBe("Request failed.");
  });
});
