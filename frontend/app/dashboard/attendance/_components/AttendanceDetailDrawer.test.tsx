// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const state = vi.hoisted(() => ({ detail: {} as Record<string, unknown>, canReview: true }));
const patch = vi.hoisted(() => vi.fn());
const showToast = vi.hoisted(() => vi.fn());
const refetch = vi.hoisted(() => vi.fn());
const refetchCorrections = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/useAttendanceDetail", () => ({ useAttendanceDetail: () => state.detail }));
vi.mock("@/hooks/usePermission", () => ({ usePermission: () => state.canReview }));
vi.mock("@/lib/clientApi", () => ({ default: { patch } }));
vi.mock("@/lib/api/endpoints", () => ({ API: { attendance: { correctionReview: (id: string) => `/attendance/corrections/${id}/review/` } } }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("./AttendanceEditForm", () => ({
  AttendanceEditForm: ({ onSaved, onCancel }: { onSaved: () => void; onCancel: () => void }) => (
    <div data-testid="edit-form"><button onClick={onSaved}>save-form</button><button onClick={onCancel}>cancel-form</button></div>
  ),
}));

import AttendanceDetailDrawer from "./AttendanceDetailDrawer";

const ABSENT = {
  record_id: "r1", employee_id: "EMP00007", name: "Aarav Nair", department: "Finance & Accounts", branch: "Mulugu", date: "2026-11-17",
  status: "Absent", status_key: "absent", clock_in: "—", clock_out: "—", total_hours: "—", overtime: "—", is_late: false, is_early_exit: false, note: "", punches: [],
};
const PRESENT = {
  ...ABSENT, status: "Late", status_key: "late", clock_in: "09:40", clock_out: "18:05", total_hours: "8h 25m", overtime: "5m", is_late: true, note: "Traffic jam",
  punches: [
    { punch_type: "IN", time: "09:40", source: "Mobile", mode: "office", is_geofence: true, distance_m: 12 },
    { punch_type: "OUT", time: "18:05", source: "Web", mode: "wfh", is_geofence: false, distance_m: 240.4, face_fallback: true },
  ],
};
const CORRECTION = (overrides: Record<string, unknown> = {}) => ({
  id: "c1", employee_id: "EMP00007", date: "2026-11-17", punch_type: "IN", requested_in: "09:00", requested_out: null, reason: "Forgot to punch",
  status: "pending", reviewed_by: null, reviewed_at: null, ...overrides,
});
const AUDIT = [
  { event: "CLOCK_IN", performed_by: "Aarav Nair", performed_at: "17 Nov 09:40", old_value: "", new_value: "", action: "Clocked in", remarks: "" },
  { event: "EDITED", performed_by: "Sria", performed_at: "18 Nov 10:00", old_value: "Late", new_value: "Present", action: "Status changed", remarks: "Approved by manager" },
];

function setDetail(record: unknown, extra: Record<string, unknown> = {}) {
  state.detail = {
    record, loading: false, error: null, refetch, corrections: [], refetchCorrections, auditEntries: [], auditLoading: false, auditError: null, ...extra,
  };
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 18, 10, 0));
  state.canReview = true;
  patch.mockReset(); showToast.mockReset(); refetch.mockReset(); refetchCorrections.mockReset();
  patch.mockResolvedValue({});
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

const open = (props: Partial<React.ComponentProps<typeof AttendanceDetailDrawer>> = {}) =>
  render(<AttendanceDetailDrawer recordId="r1" date="2026-11-17" onClose={vi.fn()} {...props} />);

describe("an absent day with no punch", () => {
  it("shows who, which day, the status in colour, and says plainly that no punch was recorded", () => {
    setDetail(ABSENT);
    open();
    expect(screen.getByText("Aarav Nair")).toBeTruthy();
    expect(screen.getByText("EMP00007 · Finance & Accounts · Mulugu")).toBeTruthy();
    expect(screen.getByText("Tuesday, 17 November 2026")).toBeTruthy();
    expect(screen.getByText(/Yesterday/)).toBeTruthy();
    const pill = screen.getByText("Absent");
    expect(pill.style.background).toMatch(/220,\s*38,\s*38/);
    expect(pill.style.color).toBe("rgb(255, 255, 255)");
    const banner = screen.getByRole("status");
    expect(within(banner).getByText("No punch recorded")).toBeTruthy();
    expect(within(banner).getByText(/use Edit to record it/)).toBeTruthy();
  });

  it("shows four quiet dashes for the times and empty states in every tab", () => {
    setDetail(ABSENT);
    open();
    expect(screen.getAllByText("—")).toHaveLength(4);
    expect(screen.getByText("No punches recorded for this day.")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: /Corrections/ }));
    expect(screen.getByText("No correction requests for this day.")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: /History/ }));
    expect(screen.getByText("No history for this record yet.")).toBeTruthy();
  });
});

describe("a day with punches", () => {
  it("shows the times as tiles, the late banner, the note and the punches as a timeline with geofence results", () => {
    setDetail(PRESENT);
    open();
    for (const value of ["09:40", "18:05", "8h 25m", "5m"]) expect(screen.getAllByText(value).length).toBeGreaterThan(0);
    expect(screen.getByText("Arrived late")).toBeTruthy();
    expect(screen.getByText("Traffic jam")).toBeTruthy();
    expect(screen.getByText("Clock In")).toBeTruthy();
    expect(screen.getByText("Clock Out")).toBeTruthy();
    expect(screen.getByText("Inside geofence")).toBeTruthy();
    expect(screen.getByText(/Outside geofence · 240 m away/)).toBeTruthy();
    expect(screen.getByText(/No Face ID: allowed by the Face ID fallback/)).toBeTruthy();
    expect(screen.getByText("Mobile")).toBeTruthy();
    expect(screen.getByText("wfh")).toBeTruthy();
    expect(screen.getByRole("tab", { name: /Punches\s*2/ }).getAttribute("aria-selected")).toBe("true");
  });
});

describe("corrections", () => {
  it("lists the requests with a coloured status and lets a reviewer approve or reject a pending one", async () => {
    setDetail(PRESENT, { corrections: [CORRECTION(), CORRECTION({ id: "c2", status: "approved", reviewed_by: "Sria", reviewed_at: "18 Nov" })] });
    open();
    fireEvent.click(screen.getByRole("tab", { name: /Corrections\s*2/ }));
    expect(screen.getByText("Pending").style.color).toMatch(/234,\s*88,\s*12/);
    expect(screen.getByText("Reviewed by Sria on 18 Nov")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /Approve|Reject/ })).toHaveLength(2);   // only the pending one has them
    fireEvent.click(screen.getByRole("button", { name: /Approve/ }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/attendance/corrections/c1/review/", { action: "approve" }));
    await waitFor(() => expect(refetchCorrections).toHaveBeenCalled());
    expect(showToast).toHaveBeenCalledWith("Correction approved. Attendance record updated.", "success");
    fireEvent.click(screen.getByRole("button", { name: /Reject/ }));
    await waitFor(() => expect(patch).toHaveBeenLastCalledWith("/attendance/corrections/c1/review/", { action: "reject" }));
  });

  it("shows no review buttons to someone who may not review, and reports a failed review", async () => {
    state.canReview = false;
    setDetail(PRESENT, { corrections: [CORRECTION()] });
    open();
    fireEvent.click(screen.getByRole("tab", { name: /Corrections/ }));
    expect(screen.queryByRole("button", { name: /Approve/ })).toBeNull();
    cleanup();
    state.canReview = true;
    patch.mockRejectedValueOnce({ message: "Already reviewed" });
    open();
    fireEvent.click(screen.getByRole("tab", { name: /Corrections/ }));
    fireEvent.click(screen.getByRole("button", { name: /Approve/ }));
    await waitFor(() => expect(showToast).toHaveBeenCalledWith("Already reviewed", "error"));
  });
});

describe("history", () => {
  it("shows the changes as a timeline with the old and new value and the remark", () => {
    setDetail(PRESENT, { auditEntries: AUDIT });
    open();
    fireEvent.click(screen.getByRole("tab", { name: /History\s*2/ }));
    expect(screen.getByText("Clock In", { selector: "span" })).toBeTruthy();
    expect(screen.getByText("Edited")).toBeTruthy();
    expect(screen.getByText("Present", { selector: "strong" })).toBeTruthy();
    expect(screen.getByText(/Approved by manager/)).toBeTruthy();
    expect(screen.getByText("Sria")).toBeTruthy();
  });

  it("shows a loading line and an error message", () => {
    setDetail(PRESENT, { auditLoading: true });
    open();
    fireEvent.click(screen.getByRole("tab", { name: /History/ }));
    expect(screen.getByText("Loading history…")).toBeTruthy();
    cleanup();
    setDetail(PRESENT, { auditError: "Could not load" });
    open();
    fireEvent.click(screen.getByRole("tab", { name: /History/ }));
    expect(screen.getByText(/Could not load/)).toBeTruthy();
  });
});

describe("editing and closing", () => {
  it("Edit opens the form in place of the button, and saving closes it and refreshes", () => {
    const onRecordChanged = vi.fn();
    setDetail(ABSENT);
    open({ onRecordChanged });
    fireEvent.click(screen.getByRole("button", { name: /Edit/ }));
    expect(screen.getByTestId("edit-form")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Edit$/ })).toBeNull();
    fireEvent.click(screen.getByText("save-form"));
    expect(screen.queryByTestId("edit-form")).toBeNull();
    expect(refetch).toHaveBeenCalled();
    expect(onRecordChanged).toHaveBeenCalled();
  });

  it("cancelling the form keeps the record as it was", () => {
    setDetail(ABSENT);
    open();
    fireEvent.click(screen.getByRole("button", { name: /Edit/ }));
    fireEvent.click(screen.getByText("cancel-form"));
    expect(screen.queryByTestId("edit-form")).toBeNull();
    expect(refetch).not.toHaveBeenCalled();
  });

  it("closes from the buttons, and from the backdrop only when the click both started and ended there", () => {
    const onClose = vi.fn();
    setDetail(ABSENT);
    const { container } = open({ onClose });
    const [headerClose, footerClose] = screen.getAllByRole("button", { name: "Close" });   // the X at the top and the button at the bottom
    fireEvent.click(headerClose);
    fireEvent.click(footerClose);
    expect(onClose).toHaveBeenCalledTimes(2);
    const overlay = container.querySelector(".drawer-overlay") as HTMLElement;
    fireEvent.click(overlay);                                                   // no mousedown on the backdrop first: ignored
    expect(onClose).toHaveBeenCalledTimes(2);
    fireEvent.mouseDown(overlay); fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("shows Loading and an error while the record loads or fails", () => {
    setDetail(null, { loading: true });
    open();
    expect(screen.getByText("Loading…")).toBeTruthy();
    cleanup();
    setDetail(null, { error: "Record not found" });
    open();
    expect(screen.getByText(/Record not found/)).toBeTruthy();
  });
});
