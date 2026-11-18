// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const mock = vi.hoisted(() => ({
  canCreate: true, loading: false, rows: [] as Array<Record<string, unknown>>, totalPages: 1, error: null as string | null,
  employeeUrls: [] as string[], overtimeUrls: [] as string[],
}));
const post = vi.hoisted(() => vi.fn());
const showToast = vi.hoisted(() => vi.fn());
const refetch = vi.hoisted(() => vi.fn());

vi.mock("@/lib/clientApi", () => ({ default: { post } }));
vi.mock("@/lib/api/endpoints", () => ({
  API: { employees: { list: "/employees/", hrList: "/employees/hr/" }, branches: { list: "/branches/" }, attendance: { overtime: "/attendance/overtime/", overtimeCreate: "/attendance/overtime/create/" } },
}));
vi.mock("@/lib/auth", () => ({ isUnrestrictedUser: () => false, getEffectiveBranch: () => "Mulugu" }));
vi.mock("@/hooks/useCurrentUser", () => ({ useCurrentUser: () => ({ id: "u1" }) }));
vi.mock("@/hooks/usePermission", () => ({ usePermission: () => mock.canCreate }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/components/BranchFilterSelect", () => ({ default: () => <div data-testid="branch-filter" /> }));
vi.mock("@/components/SearchableSelect", () => ({
  default: ({ value, onChange, options, placeholder }: { value: string; onChange: (value: string) => void; options: { value: string; label: string }[]; placeholder?: string }) => (
    <select aria-label={placeholder} value={value} onChange={event => onChange(event.target.value)}>
      <option value="">{placeholder}</option>
      {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
  ),
}));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    if (!url) return { data: null, loading: false, error: null, refetch };
    if (url.startsWith("/employees/hr/")) return { data: [{ employee_id: "HR1", full_name: "Hema Rao" }], loading: false, error: null, refetch };
    if (url.startsWith("/employees/")) { mock.employeeUrls.push(url); return { data: { results: [{ employee_id: "EMP001", full_name: "Asha Rao" }, { employee_id: "EMP002", full_name: "Durga Gadde" }] }, loading: false, error: null, refetch }; }
    if (url.startsWith("/branches/")) return { data: { results: [] }, loading: false, error: null, refetch };
    mock.overtimeUrls.push(url);
    return mock.loading
      ? { data: null, loading: true, error: null, refetch }
      : { data: { count: mock.rows.length, page: 1, total_pages: mock.totalPages, results: mock.rows }, loading: false, error: mock.error, refetch };
  },
}));

import OtEntryTab from "./OtEntryTab";

const ROW = (overrides: Record<string, unknown> = {}) => ({
  id: "o1", employee_id: "EMP001", name: "Asha Rao", initials: "AR", date: "17-11-2026", ot_hours: "2h 00m", ot_type: "Regular", ot_amount: "₹ 450", approved_by: "Hema Rao", status: "Approved", ...overrides,
});

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 18, 0, 30));      // half past midnight: the UTC date can still be the 17th in India
  mock.canCreate = true; mock.loading = false; mock.rows = []; mock.totalPages = 1; mock.error = null; mock.employeeUrls = []; mock.overtimeUrls = [];
  post.mockReset(); post.mockResolvedValue({}); showToast.mockReset(); refetch.mockReset();
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

const form = () => within(screen.getByRole("region", { name: "Add OT entry" }));
const records = () => within(screen.getByRole("region", { name: "OT records" }));
const fill = () => {
  fireEvent.change(form().getByLabelText("Select employee…"), { target: { value: "EMP002" } });
  fireEvent.change(form().getByLabelText("Select approver…"), { target: { value: "HR1" } });
  fireEvent.change(form().getByLabelText(/Reason/), { target: { value: "Month-end close" } });
};

describe("the form", () => {
  it("starts on the viewer's own today, at 18:00 to 20:00 with a 2 hour duration, and loads everyone for the picker", () => {
    render(<OtEntryTab />);
    expect((form().getByRole("textbox", { name: "" }) as HTMLInputElement | undefined)?.value ?? "").toBeDefined();
    expect(form().getByText("Wednesday")).toBeTruthy();                                       // 18 Nov 2026, not the UTC 17th
    expect((form().getByLabelText("OT Start") as HTMLInputElement).value).toBe("18:00");
    expect((form().getByLabelText("OT End") as HTMLInputElement).value).toBe("20:00");
    expect(form().getByRole("status", { name: "Overtime duration" }).textContent).toContain("2h 00m of overtime");
    expect(mock.employeeUrls[0]).toContain("page_size=500");
  });

  it("works out the duration as the times change, and warns when the end is not after the start", () => {
    render(<OtEntryTab />);
    fireEvent.change(form().getByLabelText("OT End"), { target: { value: "18:45" } });
    expect(form().getByRole("status", { name: "Overtime duration" }).textContent).toContain("45m of overtime");
    fireEvent.change(form().getByLabelText("OT End"), { target: { value: "17:00" } });
    expect(form().getByRole("status", { name: "Overtime duration" }).textContent).toContain("End must be after start");
  });

  it("offers the three types as cards showing their rate, and selects one on click", () => {
    render(<OtEntryTab />);
    const group = within(form().getByRole("radiogroup", { name: "OT type" }));
    expect(group.getByRole("radio", { name: /Regular/ }).getAttribute("aria-checked")).toBe("true");
    expect(group.getByRole("radio", { name: /Holiday/ }).textContent).toContain("2.0×");
    fireEvent.click(group.getByRole("radio", { name: /Holiday/ }));
    expect(group.getByRole("radio", { name: /Holiday/ }).getAttribute("aria-checked")).toBe("true");
    expect(group.getByRole("radio", { name: /Regular/ }).getAttribute("aria-checked")).toBe("false");
  });

  it("shows who was picked, with their ID", () => {
    render(<OtEntryTab />);
    fireEvent.change(form().getByLabelText("Select employee…"), { target: { value: "EMP001" } });
    expect(form().getByText(/· EMP001/)).toBeTruthy();
  });

  it("refuses an incomplete form in the long-standing words, and sends nothing", async () => {
    render(<OtEntryTab />);
    fireEvent.click(form().getByRole("button", { name: /Add OT Entry/ }));
    expect(form().getByRole("alert").textContent).toContain("Please select an employee.");
    fireEvent.change(form().getByLabelText("Select employee…"), { target: { value: "EMP001" } });
    fireEvent.change(form().getByLabelText("OT End"), { target: { value: "17:00" } });
    fireEvent.click(form().getByRole("button", { name: /Add OT Entry/ }));
    expect(form().getByRole("alert").textContent).toContain("OT end time must be after OT start time.");
    expect(post).not.toHaveBeenCalled();
  });

  it("sends the entry as before, thanks the person, refreshes the records and readies the next entry for the same day", async () => {
    render(<OtEntryTab />);
    fill();
    fireEvent.click(form().getByRole("radio", { name: /Weekly Off/ }));
    fireEvent.change(form().getByLabelText("OT End"), { target: { value: "21:30" } });
    fireEvent.click(form().getByRole("button", { name: /Add OT Entry/ }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/attendance/overtime/create/", {
      employee_id: "EMP002", date: "2026-11-18", ot_type: "weekly_off", ot_start: "18:00", ot_end: "21:30", approved_by: "HR1", reason: "Month-end close",
    }));
    await waitFor(() => expect(showToast).toHaveBeenCalledWith("Overtime entry created.", "success"));
    expect(refetch).toHaveBeenCalled();
    expect((form().getByLabelText("Select employee…") as HTMLSelectElement).value).toBe("");   // cleared for the next one
    expect(form().getByText("Wednesday")).toBeTruthy();                                         // the day is kept
  });

  it("shows the server's message when it refuses, and keeps what was typed", async () => {
    post.mockRejectedValueOnce({ message: "Overtime already recorded for this day." });
    render(<OtEntryTab />);
    fill();
    fireEvent.click(form().getByRole("button", { name: /Add OT Entry/ }));
    await waitFor(() => expect(form().getByRole("alert").textContent).toContain("Overtime already recorded for this day."));
    expect(showToast).toHaveBeenCalledWith("Overtime already recorded for this day.", "error");
    expect((form().getByLabelText("Select employee…") as HTMLSelectElement).value).toBe("EMP002");
  });

  it("clears the form with Reset, and hides both buttons from someone who may not create entries", () => {
    render(<OtEntryTab />);
    fill();
    fireEvent.click(form().getByRole("button", { name: "Reset" }));
    expect((form().getByLabelText("Select employee…") as HTMLSelectElement).value).toBe("");
    cleanup();
    mock.canCreate = false;
    render(<OtEntryTab />);
    expect(screen.queryByRole("button", { name: /Add OT Entry/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reset" })).toBeNull();
  });

  it("lets a future day be picked, as the old date field did", () => {
    render(<OtEntryTab />);
    expect((form().getByRole("button", { name: "Next day" }) as HTMLButtonElement).disabled).toBe(false);
  });
});

describe("the records", () => {
  it("shows each entry with a coloured type and status, hours and amount, and the total beside the heading", () => {
    mock.rows = [ROW(), ROW({ id: "o2", name: "Durga Gadde", initials: "DG", ot_type: "Holiday", status: "Pending", ot_hours: "1h 30m" })];
    render(<OtEntryTab />);
    expect(records().getByRole("heading", { name: /OT Records/ }).textContent).toContain("2");
    expect(records().getByText("Approved").style.color).toMatch(/22,\s*163,\s*74|#16A34A/i);
    expect(records().getByText("Pending").style.color).toMatch(/234,\s*88,\s*12|#EA580C/i);
    expect(records().getByText("Holiday").style.color).toMatch(/8,\s*145,\s*178|#0891B2/i);
    expect(records().getAllByText("₹ 450")).toHaveLength(2);
    expect(records().getByText("1h 30m")).toBeTruthy();
    expect(records().getByText("AR")).toBeTruthy();
  });

  it("shows a friendly empty state, a loading placeholder and an error", () => {
    render(<OtEntryTab />);
    expect(records().getByText("No overtime entries found.")).toBeTruthy();
    cleanup();
    mock.loading = true;
    render(<OtEntryTab />);
    expect(records().getAllByLabelText("Loading")).toHaveLength(3);
    expect(records().queryByText("No overtime entries found.")).toBeNull();
    cleanup();
    mock.loading = false; mock.error = "Could not load";
    render(<OtEntryTab />);
    expect(records().getByText(/Could not load/)).toBeTruthy();
  });

  it("pages through the records", () => {
    mock.rows = [ROW()]; mock.totalPages = 3;
    render(<OtEntryTab />);
    expect(records().getByText("Page 1 of 3")).toBeTruthy();
    expect((records().getByRole("button", { name: /Prev/ }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(records().getByRole("button", { name: /Next/ }));
    expect(mock.overtimeUrls[mock.overtimeUrls.length - 1]).toContain("page=2");
  });
});
