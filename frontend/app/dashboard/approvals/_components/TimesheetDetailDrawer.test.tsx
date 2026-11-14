// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { DATES, line, weekView } from "@/components/timesheet/fixtures";
import type { TimesheetWeekView } from "@/types/timesheet";

const actions = { approve: vi.fn(), sendBack: vi.fn(), unlock: vi.fn(), clearProblem: vi.fn() };
let state: { view: TimesheetWeekView | null; loading: boolean; error: string | null; isBusy: boolean; problem: string };
let requestedId: string | null = null;

vi.mock("@/hooks/useTimesheetDecision", () => ({
  useTimesheetDecision: (id: string | null) => { requestedId = id; return { ...state, ...actions }; },
}));
vi.mock("@/components/Modal", () => ({
  default: ({ title, children }: { title: string; children: React.ReactNode }) => <div role="dialog" aria-label={title}>{children}</div>,
}));

import TimesheetDetailDrawer from "./TimesheetDetailDrawer";

const submitted = (over: Partial<TimesheetWeekView> = {}): TimesheetWeekView => weekView({
  status: "submitted", is_editable: false, can_decide: true, can_unlock: false,
  totals: { daily: {}, week: "38.50", billable: "30.00", non_billable: "8.50", target: "40.00", attendance_hours: "40.00" },
  lines: [line({ entries: { [DATES[0]]: { hours: "8.00", note: "api" } } })], ...over,
});

// The dialog's button shares its name with the drawer's own "Send back" button, so look inside the dialog.
const inDialog = (name: string) => within(screen.getByRole("dialog", { name: /Send timesheet back/ })).getByRole("button", { name });
const REASON_LABEL = "Reason (the employee will see this)";
const mount = () => render(<TimesheetDetailDrawer timesheetId="T1" onClose={vi.fn()} onChanged={vi.fn()} />);

beforeEach(() => {
  Object.values(actions).forEach(mock => mock.mockReset());
  actions.approve.mockResolvedValue(true); actions.sendBack.mockResolvedValue(true); actions.unlock.mockResolvedValue(true);
  state = { view: submitted(), loading: false, error: null, isBusy: false, problem: "" };
  requestedId = null;
});
afterEach(() => cleanup());

describe("TimesheetDetailDrawer: reading", () => {
  it("shows the employee, week, the three kinds of hours and the read-only grid", () => {
    mount();
    expect(requestedId).toBe("T1");
    expect(screen.getByText("Asha Rao")).toBeTruthy();
    expect(screen.getByText("9 – 15 Nov 2026")).toBeTruthy();
    for (const hours of ["38.50", "30.00", "40.00"]) expect(screen.getAllByText(hours).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "View days for Alpha" }));
    expect((screen.getByLabelText(`Alpha hours on ${DATES[0]}`) as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText(`Alpha hours on ${DATES[0]}`) as HTMLInputElement).value).toBe("8");
  });

  it("renders nothing inside when no timesheet is open", () => {
    render(<TimesheetDetailDrawer timesheetId={null} onClose={vi.fn()} onChanged={vi.fn()} />);
    expect(screen.queryByText("Timesheet")).toBeNull();
  });

  it("shows loading and an error with no buttons", () => {
    state = { ...state, view: null, loading: true };
    const { unmount } = mount();
    expect(screen.getByText("Loading…")).toBeTruthy();
    unmount();
    state = { ...state, loading: false, error: "Timesheet not found." };
    mount();
    expect(screen.getByRole("alert").textContent).toBe("Timesheet not found.");
    expect(screen.queryByRole("button", { name: /Approve/ })).toBeNull();
  });

  it("closes from the X and from the backdrop", () => {
    const onClose = vi.fn();
    const { container } = render(<TimesheetDetailDrawer timesheetId="T1" onClose={onClose} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByLabelText("Close"));
    fireEvent.click(container.querySelector(".drawer-overlay")!);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});

describe("TimesheetDetailDrawer: deciding", () => {
  it("offers Approve and Send back only when the server says the person can decide", () => {
    mount();
    expect(screen.getByRole("button", { name: /Approve/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Send back/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Reopen for correction/ })).toBeNull();
  });

  it("offers no buttons at all to someone who can only look", () => {
    state = { ...state, view: submitted({ can_decide: false, can_unlock: false }) };
    mount();
    expect(screen.queryByRole("button", { name: /Approve|Send back|Reopen/ })).toBeNull();
  });

  it("approves with one click", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: /Approve/ }));
    expect(actions.approve).toHaveBeenCalledTimes(1);
  });

  it("disables the buttons while a decision is being made", () => {
    state = { ...state, isBusy: true };
    mount();
    expect((screen.getByRole("button", { name: /Working/ }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /Send back/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("send back asks for a reason first and sends nothing without one", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: /Send back/ }));
    expect(screen.getByRole("dialog", { name: "Send timesheet back — Asha Rao" })).toBeTruthy();
    fireEvent.click(inDialog("Send back"));
    expect(screen.getByRole("alert").textContent).toBe("Please give a reason for sending this timesheet back.");
    expect(actions.sendBack).not.toHaveBeenCalled();
  });

  it("sends back with the reason and closes the dialog when it worked", async () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: /Send back/ }));
    fireEvent.change(screen.getByLabelText(REASON_LABEL), { target: { value: "Wrong project on Monday" } });
    fireEvent.click(inDialog("Send back"));
    await waitFor(() => expect(actions.sendBack).toHaveBeenCalledWith("Wrong project on Monday"));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: /Send timesheet back/ })).toBeNull());
  });

  it("keeps the dialog and the typed reason open when the server refuses", async () => {
    actions.sendBack.mockResolvedValue(false);
    state = { ...state, problem: "This timesheet is approved, so it cannot be decided now." };
    mount();
    fireEvent.click(screen.getByRole("button", { name: /Send back/ }));
    fireEvent.change(screen.getByLabelText(REASON_LABEL), { target: { value: "reason" } });
    fireEvent.click(inDialog("Send back"));
    await waitFor(() => expect(actions.sendBack).toHaveBeenCalled());
    expect(screen.getByRole("dialog", { name: /Send timesheet back/ })).toBeTruthy();
    expect((screen.getByLabelText(REASON_LABEL) as HTMLTextAreaElement).value).toBe("reason");
    expect(screen.getByRole("alert").textContent).toContain("cannot be decided now");
  });
});

describe("TimesheetDetailDrawer: HR reopen", () => {
  beforeEach(() => { state = { ...state, view: submitted({ status: "approved", can_decide: false, can_unlock: true }) }; });

  it("offers Reopen for correction, and no Approve or Send back, on an approved sheet", () => {
    mount();
    expect(screen.getByRole("button", { name: /Reopen for correction/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Approve|Send back/ })).toBeNull();
  });

  it("needs a reason and then reopens", async () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: /Reopen for correction/ }));
    fireEvent.click(screen.getByRole("button", { name: "Reopen timesheet" }));
    expect(screen.getByRole("alert").textContent).toBe("Please give a reason for reopening this timesheet.");
    expect(actions.unlock).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(REASON_LABEL), { target: { value: "Billable flag was wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Reopen timesheet" }));
    await waitFor(() => expect(actions.unlock).toHaveBeenCalledWith("Billable flag was wrong"));
  });
});
