// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const mock = vi.hoisted(() => ({ list: [] as Array<Record<string, unknown>>, loading: false, error: null as string | null }));
const put = vi.hoisted(() => vi.fn());
const del = vi.hoisted(() => vi.fn());
const post = vi.hoisted(() => vi.fn());
const confirmDialog = vi.hoisted(() => vi.fn());
const refetch = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: mock.loading ? null : mock.list, loading: mock.loading, error: mock.error, refetch }) }));
vi.mock("@/lib/clientApi", () => ({ default: { put, delete: del, post } }));
vi.mock("@/lib/api/endpoints", () => ({ API: { leave: { policy: "/leave/policy/", policyDetail: (key: string) => `/leave/policy/${key}/` } } }));
vi.mock("@/components/DialogProvider", () => ({ confirmDialog }));
vi.mock("@/components/Modal", () => ({ default: ({ title, children, footer }: { title: React.ReactNode; children: React.ReactNode; footer: React.ReactNode }) => <div role="dialog"><h2>{title}</h2>{children}{footer}</div> }));

import { filterLeaveTypes, leaveTypeColour, summarise, type LeavePolicy } from "./leaveTypeView";
import PolicyTab from "./PolicyTab";

const POLICY = (key: string, name: string, overrides: Record<string, unknown> = {}) => ({
  id: 1, leave_type: key, leave_type_display: name, annual_days: 12, accrual_frequency: "annual", can_carry_forward: false, max_carry_forward_days: 0,
  policy_note: "", is_active: true, updated_at: "", ...overrides,
});

beforeEach(() => {
  mock.list = [POLICY("casual", "Casual Leave", { policy_note: "Max 3 consecutive days." }), POLICY("earned", "Earned Leave", { annual_days: 15, can_carry_forward: true, max_carry_forward_days: 30 }), POLICY("comp_off", "Compensatory Off", { annual_days: 0, is_active: false })];
  mock.loading = false; mock.error = null;
  [put, del, post, confirmDialog, refetch].forEach(fn => fn.mockReset());
  put.mockResolvedValue({}); del.mockResolvedValue({}); post.mockResolvedValue({}); confirmDialog.mockResolvedValue(true);
});
afterEach(cleanup);

const table = () => within(screen.getByRole("region", { name: "Leave types" }));

describe("leave type helpers", () => {
  it("keeps a colour for the known types and gives a new type the same colour every time", () => {
    expect(leaveTypeColour("casual")).toBe("#7C3AED");
    expect(leaveTypeColour("study_leave")).toBe(leaveTypeColour("study_leave"));
  });
  it("narrows by words in the name or note, and by status", () => {
    const list = mock.list as unknown as LeavePolicy[];
    expect(filterLeaveTypes(list, "casual", "all")).toHaveLength(1);
    expect(filterLeaveTypes(list, "consecutive days", "all")).toHaveLength(1);
    expect(filterLeaveTypes(list, "", "inactive").map(p => p.leave_type)).toEqual(["comp_off"]);
    expect(filterLeaveTypes(list, "leave", "active")).toHaveLength(2);
  });
  it("counts the types, the active ones, carry forward and the yearly days of the active ones", () => {
    expect(summarise(mock.list as unknown as LeavePolicy[])).toEqual({ total: 3, active: 2, carryForward: 1, annualDays: 27 });
  });
});

describe("the Leave Types tab", () => {
  it("shows the four summary numbers", () => {
    render(<PolicyTab />);
    expect(screen.getByText("Days a Year").parentElement?.nextElementSibling?.textContent).toBe("27");
    expect(screen.getByText("1 inactive")).toBeTruthy();
  });

  it("shows each type with coloured accrual and carry-forward pills and a switch for its status", () => {
    render(<PolicyTab />);
    expect(table().getByText("Yes · up to 30d").style.color).toMatch(/22,\s*163,\s*74|#16A34A/i);
    expect(table().getByText("Max 3 consecutive days.")).toBeTruthy();
    expect(table().getByRole("switch", { name: "Casual Leave active" }).getAttribute("aria-checked")).toBe("true");
    expect(table().getByRole("switch", { name: "Compensatory Off active" }).getAttribute("aria-checked")).toBe("false");
    expect(table().getByText("Custom")).toBeTruthy();
  });

  it("searches and filters the list, and says so when nothing matches", () => {
    render(<PolicyTab />);
    fireEvent.change(table().getByLabelText("Search leave types"), { target: { value: "earned" } });
    expect(table().queryByText("Casual Leave")).toBeNull();
    fireEvent.change(table().getByLabelText("Search leave types"), { target: { value: "zzz" } });
    expect(table().getByText("No leave types match.")).toBeTruthy();
    fireEvent.change(table().getByLabelText("Search leave types"), { target: { value: "" } });
    fireEvent.click(within(screen.getByRole("group", { name: "Show" })).getByRole("button", { name: "inactive" }));
    expect(table().getByText("Compensatory Off")).toBeTruthy();
    expect(table().queryByText("Casual Leave")).toBeNull();
  });

  it("flips a type on or off with the same call as before", async () => {
    render(<PolicyTab />);
    fireEvent.click(table().getByRole("switch", { name: "Casual Leave active" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith("/leave/policy/casual/", { is_active: false }));
    await waitFor(() => expect(refetch).toHaveBeenCalled());
  });

  it("deletes a custom type after asking, never a built-in one", async () => {
    render(<PolicyTab />);
    expect((table().getByRole("button", { name: "Delete Casual Leave" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(table().getByRole("button", { name: "Delete Compensatory Off" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/leave/policy/comp_off/"));
    expect(confirmDialog).toHaveBeenCalledWith('Delete "Compensatory Off"? This cannot be undone.');
  });

  it("does not delete when the person says no", async () => {
    confirmDialog.mockResolvedValue(false);
    render(<PolicyTab />);
    fireEvent.click(table().getByRole("button", { name: "Delete Compensatory Off" }));
    await waitFor(() => expect(confirmDialog).toHaveBeenCalled());
    expect(del).not.toHaveBeenCalled();
  });

  it("opens the edit window with the current values and saves them as before", async () => {
    render(<PolicyTab />);
    fireEvent.click(table().getByRole("button", { name: "Edit Earned Leave" }));
    const dialog = within(screen.getByRole("dialog"));
    fireEvent.change(dialog.getByDisplayValue("15"), { target: { value: "18" } });
    fireEvent.click(dialog.getByRole("button", { name: "Save Changes" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith("/leave/policy/earned/", expect.objectContaining({ annual_days: 18, can_carry_forward: true, max_carry_forward_days: 30 })));
  });

  it("opens the add window, checks the name, and creates the type", async () => {
    render(<PolicyTab />);
    fireEvent.click(table().getByRole("button", { name: /Add Leave Type/ }));
    const dialog = within(screen.getByRole("dialog"));
    fireEvent.click(dialog.getByRole("button", { name: "Create Leave Type" }));
    expect(dialog.getByText("Display name is required.")).toBeTruthy();
    fireEvent.change(dialog.getByPlaceholderText("e.g. Compensatory Off"), { target: { value: "Study Leave" } });
    fireEvent.click(dialog.getByRole("button", { name: "Create Leave Type" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/leave/policy/", expect.objectContaining({ leave_type_label: "Study Leave" })));
  });

  it("shows placeholders while loading, an empty state, and an error", () => {
    mock.loading = true;
    render(<PolicyTab />);
    expect(table().getAllByLabelText("Loading").length).toBeGreaterThan(0);
    cleanup();
    mock.loading = false; mock.list = [];
    render(<PolicyTab />);
    expect(table().getByText("No leave types yet.")).toBeTruthy();
    cleanup();
    mock.error = "Could not load";
    render(<PolicyTab />);
    expect(table().getByRole("alert").textContent).toContain("Could not load");
  });
});
