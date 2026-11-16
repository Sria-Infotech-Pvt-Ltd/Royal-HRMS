// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import HrRequestsTab from "./HrRequestsTab";

const urls: string[] = [];
const ticket = {
  id: "t1", request_ref: "HR-1", topic: "profile_correction", topic_display: "Profile correction", priority: "normal",
  priority_display: "Normal", message: "Section: Personal details. Field to change: Date of joining. Reason: wrong year",
  status: "open", status_display: "Open", response: "", submitted_by_name: "Asha Rao", assigned_to_name: "",
  created_at: "2026-11-16T07:55:00Z", updated_at: "2026-11-16T07:55:00Z", resolved_at: null,
};
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string) => { urls.push(url); return { data: { results: [ticket], count: 1 }, loading: false, error: null, refetch: vi.fn() }; },
}));
vi.mock("@/lib/clientApi", () => ({ default: { patch: vi.fn() } }));

afterEach(() => { cleanup(); urls.length = 0; });

describe("HrRequestsTab", () => {
  it("lists every employee's open ticket with who raised it and a Respond action", () => {
    render(<HrRequestsTab />);
    expect(urls[0]).toBe(`${API.hrHelp.list}?page_size=100&status=open`);
    expect(screen.getByText("Asha Rao")).toBeTruthy();
    expect(screen.getByText("Profile correction")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Respond" }));
    expect(screen.getByText(/Field to change: Date of joining/)).toBeTruthy();
  });

  it("filters by status, and All drops the status filter", () => {
    render(<HrRequestsTab />);
    fireEvent.click(screen.getByRole("button", { name: "Resolved" }));
    expect(urls.at(-1)).toBe(`${API.hrHelp.list}?page_size=100&status=resolved`);
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(urls.at(-1)).toBe(`${API.hrHelp.list}?page_size=100`);
  });
});
