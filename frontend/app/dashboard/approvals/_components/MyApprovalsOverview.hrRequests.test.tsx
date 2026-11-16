// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import MyApprovalsOverview from "./MyApprovalsOverview";

const urls: (string | null)[] = [];
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    urls.push(url);
    const isCorrectionCount = url?.includes("status=open&page_size=1&topic=profile_correction") ?? false;
    const data = isCorrectionCount ? { count: 3 } : { results: [], count: 0 };
    return { data, loading: false, error: null, refetch: vi.fn() };
  },
}));
vi.mock("@/hooks/useApprovalOverview", () => ({
  useApprovalOverview: () => ({ team: [], items: [], faceVisible: 0, faceAssignedToMe: 0, isLoading: false }),
}));
vi.mock("@/hooks/useTimesheetQueue", () => ({ useTimesheetPending: () => 0 }));
vi.mock("@/lib/clientApi", () => ({ default: { patch: vi.fn() } }));

const base = { canApprove: false, canApproveAttendance: false, canApproveTimesheets: false, canSeePersonnel: false, canApproveFace: false, onOpen: vi.fn() };

afterEach(() => { cleanup(); urls.length = 0; });

describe("My Approvals overview: HR requests row", () => {
  it("is absent, and fetches nothing, for people who do not answer HR Help tickets", () => {
    render(<MyApprovalsOverview {...base} canApprove />);
    expect(screen.queryByText("Profile corrections")).toBeNull();
    expect(urls.some(url => url?.startsWith(API.hrHelp.list))).toBe(false);
  });

  it("has one Profile corrections row with the open count", () => {
    render(<MyApprovalsOverview {...base} canRespondHrHelp />);
    expect(screen.getByText("Profile corrections").closest("tr")?.textContent).toContain("3");
    expect(screen.queryByText("Other HR requests")).toBeNull();
  });

  it("opens the profile corrections queue in place, not as another tab", () => {
    const onOpen = vi.fn();
    render(<MyApprovalsOverview {...base} onOpen={onOpen} canRespondHrHelp />);
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(onOpen).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Hide" })).toBeTruthy();
    expect(urls).toContain(`${API.hrHelp.list}?page_size=100&status=open&topic=profile_correction`);
  });

  it("shows the queue straight away when a link asked for it", () => {
    render(<MyApprovalsOverview {...base} canRespondHrHelp openHrRequestsInitially />);
    expect(screen.getByRole("button", { name: "Hide" })).toBeTruthy();
    expect(urls).toContain(`${API.hrHelp.list}?page_size=100&status=open&topic=profile_correction`);
  });
});
