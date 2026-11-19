// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

// The REAL form, validation and success screen; only the network, the toast, the date picker and the approval-chain preview are stubs.
const mock = vi.hoisted(() => ({
  balances: [] as Array<Record<string, unknown>>, policies: [] as Array<Record<string, unknown>>,
  preview: null as Record<string, unknown> | null, previewLoading: false,
}));
const post = vi.hoisted(() => vi.fn());
const showToast = vi.hoisted(() => vi.fn());

vi.mock("@/lib/clientApi", () => ({ default: { post } }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/hooks/useMyApprovals", () => ({ useMyApprovals: () => ({ chain: null, loading: false }) }));
vi.mock("@/components/approvals/ApprovalChainPreview", () => ({ default: () => null, chainBlocksSubmit: () => false }));
vi.mock("@/hooks/useLeaveRefresh", () => ({ notifyLeaveChanged: vi.fn() }));
vi.mock("@/components/shared/DateInput", () => ({
  default: ({ value, onChange, min }: { value: string; onChange: (iso: string) => void; min?: string }) => (
    <input aria-label={min !== undefined ? "To date" : "From date"} value={value} onChange={event => onChange(event.target.value)} />
  ),
}));
vi.mock("./LeaveHandoverFields", () => ({ default: () => null }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    if (!url) return { data: null, loading: false, error: null, refetch: vi.fn() };
    if (url.includes("action=preview")) return { data: mock.preview, loading: mock.previewLoading, error: null, refetch: vi.fn() };
    if (url.startsWith("/leave/balance/")) return { data: mock.balances, loading: false, error: null, refetch: vi.fn() };
    if (url.startsWith("/leave/policy/")) return { data: mock.policies, loading: false, error: null, refetch: vi.fn() };
    return { data: null, loading: false, error: null, refetch: vi.fn() };
  },
}));

import ApplyLeaveForm from "./ApplyLeaveForm";

const MONDAY = "2026-12-07";   // a plain working day

const POLICY = (leaveType: string, overrides: Record<string, unknown> = {}) => ({
  leave_type: leaveType, is_active: true, matches_gender_for_requester: true, annual_days: 12, grant_mode: "annual", convert_to_lop: false,
  sandwich_leave_enabled: false, policy_note: "", ...overrides,
});

beforeEach(() => {
  mock.policies = [POLICY("casual"), POLICY("sick")];
  mock.balances = [{ leave_type: "casual", available_days: 2, pending_days: 0 }, { leave_type: "sick", available_days: 5, pending_days: 0 }];
  mock.preview = { sufficient_balance: true, lop_enabled: false, actual_leave_days: 1 };
  mock.previewLoading = false;
  post.mockReset(); post.mockResolvedValue({ data: { data: { id: "lr1", total_days: 1, start_date: MONDAY, end_date: MONDAY } } });
  showToast.mockReset();
});
afterEach(cleanup);

const pickDates = (from = MONDAY, to = MONDAY) => {
  fireEvent.change(screen.getByLabelText("From date"), { target: { value: from } });
  fireEvent.change(screen.getByLabelText("To date"), { target: { value: to } });
};
const type = (reason: string) => fireEvent.change(screen.getByPlaceholderText("Reason for leave"), { target: { value: reason } });
const submit = () => fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
const submitButton = () => screen.getByRole("button", { name: "Submit request" }) as HTMLButtonElement;

describe("raising a leave request", () => {
  it("offers only the active leave types, and shows the balance preview once dates are chosen", () => {
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    expect(screen.getAllByRole("option").map(option => option.textContent)).toEqual(expect.arrayContaining(["Casual Leave", "Sick Leave"]));
    pickDates();
    expect(screen.getByText(/2 days available · 1 day requested/)).toBeTruthy();
  });

  it("does not offer a leave type that is switched off or not for this person", () => {
    mock.policies = [POLICY("casual"), POLICY("sick", { is_active: false }), POLICY("maternity", { matches_gender_for_requester: false })];
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    const labels = screen.getAllByRole("option").map(option => option.textContent);
    expect(labels).toContain("Casual Leave");
    expect(labels).not.toContain("Sick Leave");
  });

  it("asks for the dates and a reason of at least 10 characters, and sends nothing until they are there", () => {
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    submit();
    expect(screen.getByText("Start date is required.")).toBeTruthy();
    expect(screen.getByText("End date is required.")).toBeTruthy();
    expect(screen.getByText("Reason must be at least 10 characters.")).toBeTruthy();
    pickDates();
    type("short");
    submit();
    expect(screen.getByText("Reason must be at least 10 characters.")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();
  });

  it("refuses an end date before the start date", () => {
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    pickDates("2026-12-09", "2026-12-07");
    type("Family function at home");
    submit();
    expect(screen.getByText("End date must be on or after start date.")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();
  });

  it("clears a field's message as soon as that field is edited", () => {
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    submit();
    expect(screen.getByText("Reason must be at least 10 characters.")).toBeTruthy();
    type("A proper reason here");
    expect(screen.queryByText("Reason must be at least 10 characters.")).toBeNull();
  });

  it("blocks Submit and says why when there is not enough balance and the leave does not turn into unpaid leave", () => {
    mock.preview = { sufficient_balance: false, lop_enabled: false, actual_leave_days: 1 };
    mock.balances = [{ leave_type: "casual", available_days: 0, pending_days: 0 }];
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    pickDates();
    expect(screen.getByText(/0 days available · 1 day requested/)).toBeTruthy();
    expect(screen.getByText("Insufficient leave balance for the selected dates.")).toBeTruthy();
    expect(submitButton().disabled).toBe(true);
  });

  it("lets the request through when the shortfall becomes unpaid leave", () => {
    mock.preview = { sufficient_balance: false, lop_enabled: true, actual_leave_days: 1 };
    mock.balances = [{ leave_type: "casual", available_days: 0, pending_days: 0 }];
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    pickDates();
    expect(screen.queryByText("Insufficient leave balance for the selected dates.")).toBeNull();
    expect(submitButton().disabled).toBe(false);
  });

  it("shows how many days are held by pending requests", () => {
    mock.balances = [{ leave_type: "casual", available_days: 1, pending_days: 3 }];
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    pickDates();
    expect(screen.getByText(/1 day available \(after 3 pending\)/)).toBeTruthy();
  });

  it("submits the request with every field, shows the success screen, and Done closes", async () => {
    const onCancel = vi.fn();
    render(<ApplyLeaveForm onCancel={onCancel} />);
    pickDates();
    type("Sister's marriage in the family");
    submit();
    expect(await screen.findByText("Request submitted")).toBeTruthy();
    const [url, body] = post.mock.calls[0] as [string, FormData];
    expect(url).toBe("/leave/requests/");
    expect(body.get("leave_type")).toBe("casual");
    expect(body.get("duration")).toBe("full_day");
    expect(body.get("start_date")).toBe(MONDAY);
    expect(body.get("end_date")).toBe(MONDAY);
    expect(body.get("reason")).toBe("Sister's marriage in the family");
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("sends a half day for the one date chosen", async () => {
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    fireEvent.change(screen.getAllByRole("combobox")[1], { target: { value: "half_morning" } });
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: MONDAY } });
    type("Doctor appointment in the morning");
    submit();
    await screen.findByText("Request submitted");
    const body = post.mock.calls[0][1] as FormData;
    expect(body.get("duration")).toBe("half_morning");
    expect(body.get("end_date")).toBe(MONDAY);
  });

  it("shows the server's refusal on the form, keeps what was typed, and lets the person try again", async () => {
    post.mockRejectedValueOnce({ response: { data: { message: "Insufficient balance. You have 0 day(s) available." } } });
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    pickDates();
    type("Sister's marriage in the family");
    submit();
    await waitFor(() => expect(showToast).toHaveBeenCalled());
    expect(screen.getByRole("alert").textContent).toContain("Insufficient balance. You have 0 day(s) available.");
    expect((screen.getByPlaceholderText("Reason for leave") as HTMLTextAreaElement).value).toBe("Sister's marriage in the family");
    expect(submitButton().disabled).toBe(false);
    submit();
    expect(await screen.findByText("Request submitted")).toBeTruthy();
  });

  it("says so, and cannot be submitted, when no leave type is available at all", () => {
    mock.policies = [POLICY("casual", { is_active: false }), POLICY("sick", { is_active: false })];
    render(<ApplyLeaveForm onCancel={vi.fn()} />);
    expect(screen.getByText("No active leave types are available for your profile. Contact HR.")).toBeTruthy();
    expect(submitButton().disabled).toBe(true);
  });
});
