// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import type { MyCorrectionRequest } from "../../my-requests/_data";

// The REAL tab + REAL requests card; data hooks, the calendar and the request dialogs (which have their own tests) are stubs.
const refetch: Record<string, ReturnType<typeof vi.fn>> = {};
const requestedUrls: string[] = [];
const attendanceRefetch = vi.fn();
let rows: Record<string, unknown[]> = {};
let attendanceError: string | null = null;

vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    requestedUrls.push(url ?? "");
    const key = ([[API.workFromHome.requests, "wfh"], [API.attendance.myCorrections, "corrections"], [API.attendance.recentPunches, "punches"]] as const)
      .find(([prefix]) => url?.startsWith(prefix))?.[1] ?? "other";
    refetch[key] ??= vi.fn();
    const data = key === "punches" ? [] : { results: rows[key] ?? [] };
    return { data, loading: false, error: null, status: null, refetch: refetch[key] };
  },
}));
vi.mock("@/hooks/useAttendanceDashboard", () => ({ useAttendanceDashboard: () => ({ calendar: null, isLoading: false, error: attendanceError, refetch: attendanceRefetch }) }));
vi.mock("@/hooks/useWeeklyTimesheet", () => ({ useWeeklyTimesheet: () => ({ data: null, submitting: false, submit: vi.fn() }) }));
vi.mock("./EssAttendanceCalendar", () => ({ default: () => <div>calendar</div> }));
vi.mock("../../my-attendance/_components/RegularizationModal", () => ({
  default: ({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) => (
    <div role="dialog" aria-label="regularize-dialog"><button onClick={onSuccess}>stub-regularize-done</button><button onClick={onClose}>stub-close-regularize</button></div>
  ),
}));
vi.mock("../../my-requests/_components/MyCorrectionDetailModal", () => ({
  default: ({ request }: { request: { id: string } }) => <div role="dialog" aria-label="correction-detail">{request.id}</div>,
}));
vi.mock("../../work-from-home/_components/WfhRequestDetailModal", () => ({
  default: ({ request, onClose, onChanged, readOnly }: { request: { id: string }; onClose: () => void; onChanged: () => void; readOnly?: boolean }) => (
    <div role="dialog" aria-label="wfh-detail" data-readonly={String(!!readOnly)}>
      {request.id}<button onClick={onChanged}>stub-cancelled</button><button onClick={onClose}>stub-close-detail</button>
    </div>
  ),
}));
vi.mock("../../work-from-home/_components/WfhRequestModal", () => ({
  default: ({ onClose, onCreated }: { onClose: () => void; onCreated: (request: unknown) => void }) => (
    <div role="dialog" aria-label="wfh-dialog"><button onClick={() => onCreated({ id: "new" })}>stub-create-wfh</button><button onClick={onClose}>stub-close-wfh</button></div>
  ),
}));

import EssAttendanceTab from "./EssAttendanceTab";

const correction = { id: "c1", date: "2026-11-10", punch_type: "IN", status: "pending", l1_approver_name: "Asha", l2_approver_name: null, created_at: "2026-11-10T10:00:00Z" } as MyCorrectionRequest;
const wfhRequest = { id: "abcdef123456", start_date: "2026-11-20", end_date: "2026-11-22", location_label: "Home", status: "pending", created_at: "2026-11-12T10:00:00Z", l1_approver_name: "Asha", l2_approver_name: "", can_cancel: true } as WorkFromHomeRequest;

beforeEach(() => {
  for (const key of Object.keys(refetch)) delete refetch[key];
  requestedUrls.length = 0;
  attendanceRefetch.mockReset();
  rows = { corrections: [correction], wfh: [wfhRequest] };
  attendanceError = null;
});
afterEach(() => cleanup());

describe("EssAttendanceTab > Request work from home", () => {
  it("puts Request work from home beside Regularize attendance", () => {
    render(<EssAttendanceTab />);
    const wfhButton = screen.getByRole("button", { name: /Request work from home/ });
    const regularize = screen.getByRole("button", { name: "Regularize attendance" });
    expect(wfhButton.parentElement).toBe(regularize.parentElement);
  });

  it("opens the WFH dialog; saving refreshes the WFH list but not attendance or corrections", () => {
    render(<EssAttendanceTab />);
    fireEvent.click(screen.getByRole("button", { name: /Request work from home/ }));
    expect(screen.getByLabelText("wfh-dialog")).toBeTruthy();
    refetch.wfh.mockClear();
    fireEvent.click(screen.getByText("stub-create-wfh"));
    expect(refetch.wfh).toHaveBeenCalledTimes(1);
    expect(refetch.corrections).not.toHaveBeenCalled();
    expect(attendanceRefetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("stub-close-wfh"));
    expect(screen.queryByLabelText("wfh-dialog")).toBeNull();
  });

  it("leaves Regularize attendance exactly as it was", () => {
    render(<EssAttendanceTab />);
    fireEvent.click(screen.getByRole("button", { name: "Regularize attendance" }));
    expect(screen.getByLabelText("regularize-dialog")).toBeTruthy();
    expect(screen.queryByLabelText("wfh-dialog")).toBeNull();
    fireEvent.click(screen.getByText("stub-regularize-done"));
    expect(attendanceRefetch).toHaveBeenCalledTimes(1);
    expect(refetch.corrections).toHaveBeenCalledTimes(1);
    expect(refetch.wfh).not.toHaveBeenCalled();
  });

  it("lists corrections and WFH requests together, newest first, and never asks for HR help tickets", () => {
    render(<EssAttendanceTab />);
    const card = screen.getByText("Attendance requests").closest(".ess-card") as HTMLElement;
    const titles = within(card).getAllByText(/correction|Work from home/).filter(node => node.tagName === "B").map(node => node.textContent);
    // The WFH request (created 12 Nov) is newer than the correction (created 10 Nov), so it comes first.
    expect(titles).toEqual(["Work from home · Home", "10 November correction"]);
    expect(requestedUrls.some(url => url.includes(API.hrHelp.list))).toBe(false);
  });

  it("a correction row still opens its own detail", () => {
    render(<EssAttendanceTab />);
    fireEvent.click(screen.getByRole("button", { name: /10 November correction/ }));
    expect(screen.getByLabelText("correction-detail").textContent).toBe("c1");
    expect(screen.queryByLabelText("wfh-detail")).toBeNull();
  });

  it("a WFH row opens the WFH request's detail, where it can be checked or cancelled", () => {
    render(<EssAttendanceTab />);
    fireEvent.click(screen.getByRole("button", { name: /Work from home · Home/ }));
    expect(screen.getByLabelText("wfh-detail").textContent).toContain("abcdef123456");
    expect(screen.queryByLabelText("correction-detail")).toBeNull();
    refetch.wfh.mockClear();
    fireEvent.click(screen.getByText("stub-cancelled"));   // the dialog reports a cancellation
    expect(refetch.wfh).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText("stub-close-detail"));
    expect(screen.queryByLabelText("wfh-detail")).toBeNull();
  });

  it("offers View all requests when the host can take the person there, and only when there is something to view", () => {
    const onViewAll = vi.fn();
    const { unmount } = render(<EssAttendanceTab onViewAllRequests={onViewAll} />);
    fireEvent.click(screen.getByRole("button", { name: /View all requests/ }));
    expect(onViewAll).toHaveBeenCalledTimes(1);
    unmount();

    render(<EssAttendanceTab />);
    expect(screen.queryByRole("button", { name: /View all requests/ })).toBeNull();   // no host callback, no link
    cleanup();

    rows = {};
    render(<EssAttendanceTab onViewAllRequests={onViewAll} />);
    expect(screen.queryByRole("button", { name: /View all requests/ })).toBeNull();   // nothing to view
  });

  it("opens a WFH request read-only while an admin is viewing someone else's workspace", () => {
    render(<EssAttendanceTab isReadOnly />);
    fireEvent.click(screen.getByRole("button", { name: /Work from home · Home/ }));
    expect(screen.getByLabelText("wfh-detail").getAttribute("data-readonly")).toBe("true");
  });

  it("shows an empty state that mentions both ways to raise a request", () => {
    rows = {};
    render(<EssAttendanceTab />);
    expect(screen.getByText("No attendance requests yet")).toBeTruthy();
    expect(screen.getByText(/Regularize attendance if a punch was missed.*Request work from home/)).toBeTruthy();
  });

  it("hides the WFH entry, but not Regularize, while an admin is viewing someone else's workspace", () => {
    render(<EssAttendanceTab isReadOnly />);
    expect(screen.queryByRole("button", { name: /Request work from home/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Regularize attendance" })).toBeTruthy();
  });
});

describe("EssAttendanceTab: a calendar that fails to load", () => {
  it("says so and offers to try again, instead of showing an empty calendar", () => {
    attendanceError = "Server error";
    render(<EssAttendanceTab />);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Could not load your attendance");
    expect(alert.textContent).toContain("Server error");
    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(attendanceRefetch).toHaveBeenCalledTimes(1);
  });

  it("shows no warning when the calendar loaded", () => {
    render(<EssAttendanceTab />);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
