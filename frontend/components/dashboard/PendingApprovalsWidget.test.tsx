// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { API } from "@/lib/api/endpoints";
import PendingApprovalsWidget from "./PendingApprovalsWidget";

const approvals = { leave_requests: 2, expense_claims: 0, onboarding_reviews: 1, separation_requests: 0, total_pending: 3 };
let openTickets: { count: number } | null = { count: 4 };

vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string) => ({
    data: url === API.dashboard.pendingApprovals ? approvals : openTickets,
    loading: false,
    refetch: vi.fn(),
  }),
}));

afterEach(() => { cleanup(); openTickets = { count: 4 }; });

describe("PendingApprovalsWidget", () => {
  it("shows open profile corrections as a row that opens the queue, and counts them in the total", () => {
    render(<PendingApprovalsWidget />);
    const row = screen.getByText("Profile Corrections").closest("a");
    expect(row?.getAttribute("href")).toBe("/dashboard/approvals?section=hr_requests");
    expect(row?.textContent).toContain("4");
    expect(screen.getByText("7 pending")).toBeTruthy();
  });

  it("shows 0 tickets while the count is not available", () => {
    openTickets = null;
    render(<PendingApprovalsWidget />);
    expect(screen.getByText("Profile Corrections").closest("a")?.textContent).toContain("0");
    expect(screen.getByText("3 pending")).toBeTruthy();
  });
});
