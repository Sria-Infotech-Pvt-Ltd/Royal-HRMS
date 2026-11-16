// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import type { WorkFromHomeRequest } from "@/types/workFromHome";

// The REAL dialog; only the network, the toast and the confirm prompt are replaced.
const patch = vi.fn();
const showToast = vi.fn();
const confirmDialog = vi.fn();
vi.mock("@/lib/clientApi", () => ({ default: { patch: (...args: unknown[]) => patch(...args) }, isSessionKnownExpired: () => false }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/components/DialogProvider", () => ({ confirmDialog: (...args: unknown[]) => confirmDialog(...args) }));

import WfhRequestDetailModal from "./WfhRequestDetailModal";

const request = (over: Partial<WorkFromHomeRequest> = {}): WorkFromHomeRequest => ({
  id: "wfh-1", start_date: "2026-11-20", end_date: "2026-11-22", reason: "Plumber visit", location_label: "Home", latitude: "17.1", longitude: "78.1",
  status: "pending", employee_name: "Test", employee_code: "10000001", employee_dept: "Web", employee_branch: "Sria",
  l1_approver_name: "Asha Rao", l1_status: null, l1_remarks: "", l1_actioned_at: null, l2_approver_name: "", l2_status: null, l2_remarks: "",
  l2_actioned_at: null, created_at: "2026-11-12T10:00:00Z", can_approve: false, can_cancel: true, ...over,
});

beforeEach(() => {
  patch.mockReset(); showToast.mockReset(); confirmDialog.mockReset();
  patch.mockResolvedValue({ data: { message: "Work from home request cancelled." } });
  confirmDialog.mockResolvedValue(true);
});
afterEach(() => cleanup());

/** The dialog header also has an X button labelled "Close", so the footer's own button is looked up inside the footer. */
const footer = () => within(screen.getByRole("dialog").querySelector(".modal-footer") as HTMLElement);

function open(over: Partial<WorkFromHomeRequest> = {}, extra: { readOnly?: boolean } = {}) {
  const onClose = vi.fn();
  const onChanged = vi.fn();
  render(<WfhRequestDetailModal request={request(over)} onClose={onClose} onChanged={onChanged} {...extra} />);
  return { onClose, onChanged };
}

describe("WfhRequestDetailModal", () => {
  it("shows the dates, length, location, reason, status, approver and submission date", () => {
    open();
    const text = screen.getByRole("dialog").textContent ?? "";
    expect(text).toContain("3 days");
    expect(text).toContain("Home");
    expect(text).toContain("Plumber visit");
    expect(text).toContain("Pending");
    expect(text).toContain("Asha Rao");
    expect(text).toContain("Submitted");
  });

  it("shows the approvers' decisions and remarks, and HR approval only when there is an HR approver", () => {
    open({ status: "l2_pending", l1_status: "approved", l1_remarks: "Fine by me", l2_approver_name: "Hari Babu" });
    const text = screen.getByRole("dialog").textContent ?? "";
    expect(text).toContain("L2 Pending");
    expect(text).toContain("Fine by me");
    expect(text).toContain("HR Approval");
    expect(text).toContain("Hari Babu");
    cleanup();
    open();
    expect(screen.getByRole("dialog").textContent).not.toContain("HR Approval");
  });

  it("cancels a pending request after confirming: PATCHes the request, tells the host, toasts, closes", async () => {
    const { onClose, onChanged } = open();
    fireEvent.click(screen.getByRole("button", { name: "Cancel request" }));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(confirmDialog).toHaveBeenCalledTimes(1);
    expect(patch).toHaveBeenCalledTimes(1);
    expect(patch).toHaveBeenCalledWith(API.workFromHome.requestDetail("wfh-1"));
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(showToast).toHaveBeenCalledWith("Work from home request cancelled.", "success");
  });

  it("does nothing when the person declines the confirmation", async () => {
    confirmDialog.mockResolvedValue(false);
    const { onClose, onChanged } = open();
    fireEvent.click(screen.getByRole("button", { name: "Cancel request" }));
    await waitFor(() => expect(confirmDialog).toHaveBeenCalledTimes(1));
    expect(patch).not.toHaveBeenCalled();
    expect(onChanged).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("keeps the dialog open and shows the server's reason when the cancel is refused", async () => {
    patch.mockRejectedValue({ response: { data: { message: "Only pending requests can be cancelled." } } });
    const { onClose, onChanged } = open();
    fireEvent.click(screen.getByRole("button", { name: "Cancel request" }));
    await waitFor(() => expect(showToast).toHaveBeenCalledWith("Only pending requests can be cancelled.", "error"));
    expect(onChanged).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Cancel request" })).toBeTruthy();   // usable again
  });

  it("offers no Cancel for an approved request, and says why instead of leaving a missing button unexplained", () => {
    open({ status: "approved", can_cancel: false, l1_status: "approved" });
    expect(screen.queryByRole("button", { name: "Cancel request" })).toBeNull();
    expect(screen.getByRole("dialog").textContent).toContain("can't be cancelled from here");
    expect(screen.getByRole("dialog").textContent).toContain("Approved");
  });

  it("offers no Cancel (and no approved-request note) for a request that is already rejected or cancelled", () => {
    open({ status: "rejected", can_cancel: false, l1_status: "rejected", l1_remarks: "Team is short that week" });
    expect(screen.queryByRole("button", { name: "Cancel request" })).toBeNull();
    expect(screen.getByRole("dialog").textContent).toContain("Team is short that week");
    expect(screen.getByRole("dialog").textContent).not.toContain("can't be cancelled from here");
  });

  it("hides Cancel while an admin is viewing someone else's workspace", () => {
    open({}, { readOnly: true });
    expect(screen.queryByRole("button", { name: "Cancel request" })).toBeNull();
    expect(footer().getByRole("button", { name: "Close" })).toBeTruthy();
  });

  it("closes from the Close button without touching the request", () => {
    const { onClose, onChanged } = open();
    fireEvent.click(footer().getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onChanged).not.toHaveBeenCalled();
    expect(patch).not.toHaveBeenCalled();
  });
});
