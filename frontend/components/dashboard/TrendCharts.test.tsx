// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: () => ({
    loading: false,
    data: { series: [
      { label: "Oct 2026", month: "2026-10", approved: 3, rejected: 0 },
      { label: "Nov 2026", month: "2026-11", approved: 0, rejected: 5 },
    ] },
  }),
}));

import { LeaveTrendCard } from "./TrendCharts";

beforeEach(() => push.mockClear());
afterEach(cleanup);

describe("LeaveTrendCard bars", () => {
  it("opens that month's rejected requests when the rejected bar is clicked", () => {
    render(<LeaveTrendCard />);
    fireEvent.click(screen.getByRole("button", { name: "Nov 2026: 5 rejected" }));
    expect(push).toHaveBeenCalledWith("/dashboard/approvals?section=approvals&type=leave&status=rejected&month=2026-11");
  });

  it("opens the approved ones from the approved bar", () => {
    render(<LeaveTrendCard />);
    fireEvent.click(screen.getByRole("button", { name: "Oct 2026: 3 approved" }));
    expect(push).toHaveBeenCalledWith("/dashboard/approvals?section=approvals&type=leave&status=approved&month=2026-10");
  });

  it("does not also trigger the card around it (the HR dashboard links the whole card to the Leave page)", () => {
    const outer = vi.fn();
    render(<div onClick={outer}><LeaveTrendCard /></div>);
    fireEvent.click(screen.getByRole("button", { name: "Nov 2026: 5 rejected" }));
    expect(outer).not.toHaveBeenCalled();
  });

  it("the legend words Approved / Rejected open that status too, for every month, without triggering the card around them", () => {
    const outer = vi.fn();
    render(<div onClick={outer}><LeaveTrendCard /></div>);
    fireEvent.click(screen.getByRole("button", { name: "Rejected" }));
    expect(push).toHaveBeenCalledWith("/dashboard/approvals?section=approvals&type=leave&status=rejected");
    fireEvent.click(screen.getByRole("button", { name: "Approved" }));
    expect(push).toHaveBeenLastCalledWith("/dashboard/approvals?section=approvals&type=leave&status=approved");
    expect(outer).not.toHaveBeenCalled();
  });

  it("leaves a bar with nothing behind it as plain, not a button", () => {
    render(<LeaveTrendCard />);
    expect(screen.queryByRole("button", { name: "Nov 2026: 0 approved" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Oct 2026: 0 rejected" })).toBeNull();
  });
});
