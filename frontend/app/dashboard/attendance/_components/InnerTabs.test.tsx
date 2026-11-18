// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const mock = vi.hoisted(() => ({
  canEdit: true, loading: false, error: null as string | null, urls: [] as string[],
  data: {} as Record<string, unknown>, totalPages: 1,
}));
const patch = vi.hoisted(() => vi.fn());
const showToast = vi.hoisted(() => vi.fn());
const refetch = vi.hoisted(() => vi.fn());

vi.mock("@/lib/clientApi", () => ({ default: { patch, post: vi.fn() } }));
vi.mock("@/lib/auth", () => ({ isUnrestrictedUser: () => false, getEffectiveBranch: () => "Mulugu" }));
vi.mock("@/hooks/useCurrentUser", () => ({ useCurrentUser: () => ({ id: "u1" }) }));
vi.mock("@/hooks/usePermission", () => ({ usePermission: () => mock.canEdit }));
vi.mock("@/hooks/useDepartmentOptions", () => ({ useDepartmentOptions: () => ["Sales"] }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/components/BranchFilterSelect", () => ({ default: () => <div data-testid="branch-filter" /> }));
vi.mock("@/components/shared/DateInput", () => ({ default: ({ value }: { value: string }) => <input aria-label="Date" readOnly value={value} /> }));
vi.mock("./AssignPunchModal", () => ({ default: () => <div>assign modal</div> }));
vi.mock("./DiscardPunchModal", () => ({ default: () => <div>discard modal</div> }));
vi.mock("./ConvertPunchModal", () => ({ default: () => <div>convert modal</div> }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    if (!url) return { data: null, loading: false, error: null, refetch };
    mock.urls.push(url);
    const key = Object.keys(mock.data).find(prefix => url.startsWith(prefix));
    if (!key) return { data: { results: [] }, loading: false, error: null, refetch };
    const results = mock.data[key] as unknown[];
    return mock.loading
      ? { data: null, loading: true, error: null, refetch }
      : { data: { count: results.length, page: 1, total_pages: mock.totalPages, results }, loading: false, error: mock.error, refetch };
  },
}));

import { API } from "@/lib/api/endpoints";
import InvalidPunchesTab from "./InvalidPunchesTab";
import UnpunchesTab from "./UnpunchesTab";
import CorrectionsTab from "./CorrectionsTab";
import WeeklyOffAssignmentTab from "./WeeklyOffAssignmentTab";

const CORRECTION = (overrides: Record<string, unknown> = {}) => ({
  id: "c1", employee_id: "EMP001", name: "Asha Rao", department: "Sales", branch: "Mulugu", date: "17-11-2026", punch_type: "IN",
  requested_in: "09:05", requested_out: null, reason: "Forgot to punch", status: "pending", l1_approver_name: "Hema Rao", l2_approver_name: null,
  l1_status: null, l2_status: null, reviewed_by: null, reviewed_at: null, can_action: true, ...overrides,
});

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 18, 0, 30));
  mock.canEdit = true; mock.loading = false; mock.error = null; mock.urls = []; mock.data = {}; mock.totalPages = 1;
  patch.mockReset(); patch.mockResolvedValue({}); showToast.mockReset(); refetch.mockReset();
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("Invalid Punches", () => {
  const punch = (overrides: Record<string, unknown> = {}) => ({ id: "p1", device_id: "DEV-1", raw_time: "17-11-2026 09:00", biometric_id: "B77", issue_type: "no-match", issue: "No matching employee", suggested_match: "Asha Rao", branch: "Mulugu", ...overrides });

  it("shows each punch with a coloured issue, the total, and the three actions", () => {
    mock.data = { [API.attendance.invalidPunches]: [punch(), punch({ id: "p2", issue_type: "duplicate", issue: "Duplicate punch" })] };
    render(<InvalidPunchesTab />);
    const card = within(screen.getByRole("region", { name: "Invalid Punches" }));
    expect(card.getByLabelText("2 in total")).toBeTruthy();
    expect(card.getByText("No matching employee").style.color).toMatch(/220,\s*38,\s*38|#DC2626/i);
    expect(card.getByText("Duplicate punch").style.color).toMatch(/234,\s*88,\s*12|#EA580C/i);
    expect(card.getAllByRole("button", { name: /Assign/ })).toHaveLength(2);
    fireEvent.click(card.getAllByRole("button", { name: /Discard/ })[0]);
    expect(screen.getByText("discard modal")).toBeTruthy();
  });

  it("hides the actions from someone who may not edit, and shows empty, loading and error states", () => {
    mock.canEdit = false;
    mock.data = { [API.attendance.invalidPunches]: [punch()] };
    render(<InvalidPunchesTab />);
    expect(screen.queryByRole("button", { name: /Assign/ })).toBeNull();
    cleanup();
    mock.data = {};
    render(<InvalidPunchesTab />);
    expect(screen.getByText("No invalid punches found.")).toBeTruthy();
    cleanup();
    mock.data = { [API.attendance.invalidPunches]: [] }; mock.loading = true;
    render(<InvalidPunchesTab />);
    expect(screen.getAllByLabelText("Loading")).toHaveLength(3);
    cleanup();
    mock.loading = false; mock.error = "Could not load";
    render(<InvalidPunchesTab />);
    expect(screen.getByRole("alert").textContent).toContain("Could not load");
  });

  it("pages through the punches", () => {
    mock.data = { [API.attendance.invalidPunches]: [punch()] }; mock.totalPages = 2;
    render(<InvalidPunchesTab />);
    fireEvent.click(screen.getByRole("button", { name: /Next/ }));
    expect(mock.urls[mock.urls.length - 1]).toContain("page=2");
  });
});

describe("Un-punches", () => {
  it("starts on the viewer's own today and shows the person with their ID and a coloured correction status", () => {
    mock.data = { [API.attendance.unPunches]: [
      { employee_id: "EMP001", name: "Asha Rao", branch: "Mulugu", date: "18-11-2026", clock_in: "09:02", expected_out: "18:00", correction_pending: true },
      { employee_id: "EMP002", name: "Durga Gadde", branch: "Mulugu", date: "18-11-2026", clock_in: "09:10", expected_out: "18:00", correction_pending: false },
    ] };
    render(<UnpunchesTab />);
    expect((screen.getByLabelText("Date") as HTMLInputElement).value).toBe("2026-11-18");   // not the UTC 17th
    expect(mock.urls.some(url => url.includes("date=2026-11-18"))).toBe(true);
    expect(screen.getByText("EMP002")).toBeTruthy();
    expect(screen.getByText("Correction Submitted").style.color).toMatch(/234,\s*88,\s*12|#EA580C/i);
    expect(screen.getByText("No Correction Filed").style.color).toMatch(/100,\s*116,\s*139|#64748B/i);
  });

  it("shows a friendly message when nobody is missing a clock-out", () => {
    render(<UnpunchesTab />);
    expect(screen.getByText("No un-punches found for this date.")).toBeTruthy();
  });
});

describe("Corrections", () => {
  it("asks for the pending ones first, and the status buttons change the list", () => {
    mock.data = { [API.attendance.corrections]: [CORRECTION()] };
    render(<CorrectionsTab />);
    expect(mock.urls[0]).toContain("status=pending");
    const group = within(screen.getByRole("group", { name: "Status" }));
    expect(group.getByRole("button", { name: "Pending — Manager" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(group.getByRole("button", { name: "Approved" }));
    expect(mock.urls[mock.urls.length - 1]).toContain("status=approved");
    fireEvent.click(group.getByRole("button", { name: "All" }));
    expect(mock.urls[mock.urls.length - 1]).not.toContain("status=");
  });

  it("shows the request with a coloured status and who it waits for, and approves with the same call as before", async () => {
    mock.data = { [API.attendance.corrections]: [CORRECTION()] };
    render(<CorrectionsTab />);
    expect(screen.getByText("Pending (Manager)").style.color).toMatch(/234,\s*88,\s*12|#EA580C/i);
    expect(screen.getByText("Awaiting Hema Rao")).toBeTruthy();
    expect(screen.getByText("Clock In")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith(API.attendance.correctionReview("c1"), { action: "approve" }));
    await waitFor(() => expect(showToast).toHaveBeenCalledWith("Correction approved. Attendance record updated.", "success"));
    expect(refetch).toHaveBeenCalled();
  });

  it("rejects, and shows the server's message when that fails", async () => {
    patch.mockRejectedValueOnce({ message: "Already reviewed." });
    mock.data = { [API.attendance.corrections]: [CORRECTION()] };
    render(<CorrectionsTab />);
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith(API.attendance.correctionReview("c1"), { action: "reject" }));
    await waitFor(() => expect(showToast).toHaveBeenCalledWith("Already reviewed.", "error"));
  });

  it("shows no buttons when the person may not act on it, only the review history", () => {
    mock.data = { [API.attendance.corrections]: [CORRECTION({ status: "approved", can_action: false, l1_status: "approved", reviewed_at: "18-11-2026" })] };
    render(<CorrectionsTab />);
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.getByText(/L1: Hema Rao — approved/)).toBeTruthy();
    expect(screen.getByText("Approved", { selector: "span" }).style.color).toMatch(/22,\s*163,\s*74|#16A34A/i);
  });

  it("shows an empty state naming what to do next", () => {
    render(<CorrectionsTab />);
    expect(screen.getByText("No correction requests found.")).toBeTruthy();
  });
});

describe("Weekly Off Assignment", () => {
  const assignment = (overrides: Record<string, unknown> = {}) => ({ employee_id: "EMP001", employee_name: "Asha Rao", department: "Sales", branch: "Mulugu", pattern_id: "w1", pattern_name: "Sunday Off", effective_from: "01-11-2026", effective_to: null, status: "Assigned", ...overrides });

  it("shows the pattern and status as pills, the total, and Change or Assign by status", () => {
    mock.data = { [API.attendance.weeklyOffAssignments]: [assignment(), assignment({ employee_id: "EMP002", employee_name: "Durga Gadde", pattern_id: null, pattern_name: null, effective_from: null, status: "Not Assigned" })] };
    render(<WeeklyOffAssignmentTab />);
    const card = within(screen.getByRole("region", { name: "Weekly Off Assignment" }));
    expect(card.getByLabelText("2 in total")).toBeTruthy();
    expect(card.getByText("Sunday Off")).toBeTruthy();
    expect(card.getByText("Assigned", { selector: "span" }).style.color).toMatch(/22,\s*163,\s*74|#16A34A/i);
    expect(card.getByText("Not Assigned", { selector: "span" })).toBeTruthy();
    expect(card.getByRole("button", { name: /Change/ })).toBeTruthy();
    expect(card.getByRole("button", { name: /^\s*Assign/ })).toBeTruthy();
  });

  it("opens the assign window, defaulting the date to the viewer's own today", () => {
    mock.data = { [API.attendance.weeklyOffAssignments]: [assignment()] };
    render(<WeeklyOffAssignmentTab />);
    fireEvent.click(screen.getByRole("button", { name: /Change/ }));
    expect(screen.getByText("Assign Weekly Off Pattern")).toBeTruthy();
    expect((screen.getAllByLabelText("Date")[0] as HTMLInputElement).value).toBe("2026-11-18");
  });

  it("offers Bulk Assign only to someone who may assign, and shows an empty state", () => {
    render(<WeeklyOffAssignmentTab />);
    expect(screen.getByRole("button", { name: /Bulk Assign/ })).toBeTruthy();
    expect(screen.getByText("No employees found.")).toBeTruthy();
    cleanup();
    mock.canEdit = false;
    render(<WeeklyOffAssignmentTab />);
    expect(screen.queryByRole("button", { name: /Bulk Assign/ })).toBeNull();
  });
});
