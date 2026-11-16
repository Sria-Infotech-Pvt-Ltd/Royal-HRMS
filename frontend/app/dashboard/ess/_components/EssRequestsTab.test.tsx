// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import type { WorkFromHomeRequest } from "@/types/workFromHome";

// The REAL tab + REAL chooser + REAL dialog shell; data hooks and the request dialogs (which have their own tests) are stubs.
const showToast = vi.fn();
const refetch: Record<string, ReturnType<typeof vi.fn>> = {};
let rows: Record<string, unknown[]> = {};

vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    const key = ([
      [API.workFromHome.requests, "wfh"], [API.hrHelp.list, "hrHelp"], [API.leave.requests, "leave"],
      [API.expenses.list, "expenses"], [API.attendance.myCorrections, "corrections"],
    ] as const).find(([prefix]) => url?.startsWith(prefix))?.[1] ?? "other";
    refetch[key] ??= vi.fn();
    return { data: { results: rows[key] ?? [] }, loading: false, error: null, status: null, refetch: refetch[key] };
  },
}));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/lib/clientApi", () => ({ default: { patch: vi.fn() }, isSessionKnownExpired: () => false }));
vi.mock("../../leave/_components/LeaveRequestDetailModal", () => ({ default: () => null }));
vi.mock("../../expenses/_components/ExpenseDetailModal", () => ({ default: () => null }));
vi.mock("../../my-requests/_components/MyCorrectionDetailModal", () => ({ default: () => null }));
vi.mock("../../my-requests/_components/HrHelpDetailModal", () => ({ default: () => null }));
vi.mock("../../my-requests/_components/EmployeeRequestModal", () => ({
  default: ({ onClose, onSubmitted }: { onClose: () => void; onSubmitted: () => void }) => (
    <div role="dialog" aria-label="hr-help-dialog"><button onClick={onSubmitted}>stub-submit-hr</button><button onClick={onClose}>stub-close-hr</button></div>
  ),
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

import EssRequestsTab from "./EssRequestsTab";

const wfhRequest = { id: "abcdef123456", start_date: "2026-11-20", end_date: "2026-11-22", location_label: "Home", status: "pending", created_at: "2026-11-12T10:00:00Z", l1_approver_name: "Asha", l2_approver_name: "", can_cancel: true } as WorkFromHomeRequest;

beforeEach(() => {
  showToast.mockReset();
  for (const key of Object.keys(refetch)) delete refetch[key];
  rows = { wfh: [wfhRequest] };
});
afterEach(() => cleanup());

describe("EssRequestsTab > opening an existing request", () => {
  it("a WFH row opens the WFH request's detail (it used to do nothing), and a cancellation refreshes the WFH list", () => {
    render(<EssRequestsTab />);
    fireEvent.click(screen.getByRole("button", { name: /Open request WFH-ABCDEF/ }));
    expect(screen.getByLabelText("wfh-detail").textContent).toContain("abcdef123456");
    fireEvent.click(screen.getByText("stub-cancelled"));
    expect(refetch.wfh).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText("stub-close-detail"));
    expect(screen.queryByLabelText("wfh-detail")).toBeNull();
  });

  it("opens it read-only while an admin is viewing someone else's workspace", () => {
    render(<EssRequestsTab isReadOnly />);
    fireEvent.click(screen.getByRole("button", { name: /Open request WFH-ABCDEF/ }));
    expect(screen.getByLabelText("wfh-detail").getAttribute("data-readonly")).toBe("true");
  });
});

describe("EssRequestsTab > New request", () => {
  it("keeps the request register, including work-from-home requests", () => {
    render(<EssRequestsTab />);
    expect(screen.getByText(/WFH-ABCDEF · Home/)).toBeTruthy();
  });

  it("asks what kind of request first, offering HR help and Work from home", () => {
    render(<EssRequestsTab />);
    fireEvent.click(screen.getByRole("button", { name: "New request" }));
    expect(screen.getByRole("button", { name: /HR help request/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Work from home request/ })).toBeTruthy();
    expect(screen.queryByLabelText("hr-help-dialog")).toBeNull();
    expect(screen.queryByLabelText("wfh-dialog")).toBeNull();
  });

  it("HR help opens the existing HR help dialog and behaves exactly as before", () => {
    render(<EssRequestsTab />);
    fireEvent.click(screen.getByRole("button", { name: "New request" }));
    fireEvent.click(screen.getByRole("button", { name: /HR help request/ }));
    expect(screen.queryByRole("button", { name: /Work from home request/ })).toBeNull();   // the chooser is gone
    fireEvent.click(screen.getByText("stub-submit-hr"));
    expect(showToast).toHaveBeenCalledWith("Your request was submitted.", "success");
    expect(refetch.hrHelp).toHaveBeenCalledTimes(1);
    expect(refetch.wfh).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("hr-help-dialog")).toBeNull();
  });

  it("Work from home opens the WFH dialog; saving refreshes only the WFH list, once", () => {
    render(<EssRequestsTab />);
    fireEvent.click(screen.getByRole("button", { name: "New request" }));
    fireEvent.click(screen.getByRole("button", { name: /Work from home request/ }));
    expect(screen.getByLabelText("wfh-dialog")).toBeTruthy();
    fireEvent.click(screen.getByText("stub-create-wfh"));
    expect(refetch.wfh).toHaveBeenCalledTimes(1);
    expect(refetch.hrHelp).not.toHaveBeenCalled();
    expect(showToast).not.toHaveBeenCalled();   // the form shows its own success screen
    fireEvent.click(screen.getByText("stub-close-wfh"));
    expect(screen.queryByLabelText("wfh-dialog")).toBeNull();
    expect(refetch.wfh).toHaveBeenCalledTimes(1);   // closing does not refetch again
  });

  it("closing the chooser opens nothing", () => {
    render(<EssRequestsTab />);
    fireEvent.click(screen.getByRole("button", { name: "New request" }));
    fireEvent.click(screen.getByLabelText("Close"));
    expect(screen.queryByRole("button", { name: /HR help request/ })).toBeNull();
    expect(screen.queryByLabelText("hr-help-dialog")).toBeNull();
    expect(screen.queryByLabelText("wfh-dialog")).toBeNull();
  });

  it("while an admin is viewing someone else's workspace, New request goes straight to HR help as before", () => {
    render(<EssRequestsTab isReadOnly />);
    fireEvent.click(screen.getByRole("button", { name: "New request" }));
    expect(screen.getByLabelText("hr-help-dialog")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Work from home request/ })).toBeNull();
  });
});
