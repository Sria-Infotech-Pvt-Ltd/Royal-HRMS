// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import type { WFHSavedLocation, WorkFromHomeRequest } from "@/types/workFromHome";

// The REAL dialog + REAL RequestWfhForm (validation, saved locations, POST); only the network and the toast are replaced.
const get = vi.fn();
const post = vi.fn();
const showToast = vi.fn();
vi.mock("@/lib/clientApi", () => ({
  default: { get: (...args: unknown[]) => get(...args), post: (...args: unknown[]) => post(...args), delete: vi.fn() },
  isSessionKnownExpired: () => false,
}));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));

import RequestWfhForm from "./RequestWfhForm";
import WfhRequestModal from "./WfhRequestModal";

const HOME: WFHSavedLocation = { id: "loc-1", label: "Home", latitude: "17.462542", longitude: "78.369547", created_at: "2026-11-01T00:00:00Z" };
const envelope = <T,>(data: T) => ({ data: { status: "success", message: "", data } });
const created = { id: "wfh-1", start_date: "2026-11-20", end_date: "2026-11-22", status: "pending" } as WorkFromHomeRequest;   // only the fields the success screen reads

beforeEach(() => {
  get.mockReset(); post.mockReset(); showToast.mockReset();
  get.mockImplementation(async (url: string) => envelope(url === API.workFromHome.savedLocations ? [HOME] : []));
  post.mockResolvedValue(envelope(created));
});
afterEach(() => cleanup());

const reasonBox = () => screen.getByPlaceholderText(/Why do you need to work from home/);

/** Fills the dates and (unless told not to) the reason, which every request must have. */
async function fillDates(start = "20/11/2026", end = "22/11/2026", reason: string | null = "Internet repair") {
  const [startBox, endBox] = screen.getAllByPlaceholderText("DD-MM-YYYY");
  fireEvent.change(startBox, { target: { value: start } });
  fireEvent.change(endBox, { target: { value: end } });
  if (reason !== null) fireEvent.change(reasonBox(), { target: { value: reason } });
  await screen.findByText("Latitude");   // the saved location has been applied
}

describe("WfhRequestModal", () => {
  it("opens the existing form in a dialog, with the Submit button inside it", async () => {
    render(<WfhRequestModal onClose={vi.fn()} onCreated={vi.fn()} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveProperty("textContent", expect.stringContaining("Request work from home"));
    expect(screen.getByRole("button", { name: "Submit Request" })).toBeTruthy();
    await screen.findByText("Latitude");
  });

  it("refuses an empty submit with the form's own messages and sends nothing", async () => {
    const onCreated = vi.fn();
    render(<WfhRequestModal onClose={vi.fn()} onCreated={onCreated} />);
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    expect(await screen.findByText("Start date is required.")).toBeTruthy();
    expect(screen.getByText("End date is required.")).toBeTruthy();
    expect(screen.getByText("Reason is required.")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("marks the reason as required, and will not submit without one even when everything else is filled", async () => {
    render(<WfhRequestModal onClose={vi.fn()} onCreated={vi.fn()} />);
    await fillDates("20/11/2026", "22/11/2026", null);
    expect(reasonBox().getAttribute("aria-required")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    expect(await screen.findByText("Reason is required.")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();
  });

  it("treats a reason of only spaces as missing", async () => {
    render(<WfhRequestModal onClose={vi.fn()} onCreated={vi.fn()} />);
    await fillDates("20/11/2026", "22/11/2026", "     ");
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    expect(await screen.findByText("Reason is required.")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();
  });

  it("clears the reason message as soon as the person starts typing one", async () => {
    render(<WfhRequestModal onClose={vi.fn()} onCreated={vi.fn()} />);
    await fillDates("20/11/2026", "22/11/2026", null);
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    await screen.findByText("Reason is required.");
    fireEvent.change(reasonBox(), { target: { value: "Doctor visit" } });
    expect(screen.queryByText("Reason is required.")).toBeNull();
  });

  it("sends the reason trimmed", async () => {
    render(<WfhRequestModal onClose={vi.fn()} onCreated={vi.fn()} />);
    await fillDates("20/11/2026", "22/11/2026", "  Plumber visiting  ");
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    await screen.findByText("Request Submitted!");
    expect(post.mock.calls[0][1].reason).toBe("Plumber visiting");
  });

  it("rejects an end date before the start date without calling the API", async () => {
    render(<WfhRequestModal onClose={vi.fn()} onCreated={vi.fn()} />);
    await fillDates("22/11/2026", "20/11/2026");
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    // DateInput's own min bound clears an end date that precedes the start, so the form reports it as missing.
    expect(await screen.findByText(/End date/)).toBeTruthy();
    expect(post).not.toHaveBeenCalled();
  });

  it("submits to the same endpoint, tells the host once, shows the success screen, and Done closes the dialog", async () => {
    const onCreated = vi.fn();
    const onClose = vi.fn();
    render(<WfhRequestModal onClose={onClose} onCreated={onCreated} />);
    await fillDates();
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));

    expect(await screen.findByText("Request Submitted!")).toBeTruthy();
    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith(API.workFromHome.requests, {
      start_date: "2026-11-20", end_date: "2026-11-22", reason: "Internet repair", location_label: "Home", latitude: 17.462542, longitude: 78.369547,
      location_source: "gps", saved_location_id: "loc-1",
    });
    expect(onCreated).toHaveBeenCalledTimes(1);          // the host is told as soon as it is saved ...
    expect(onCreated).toHaveBeenCalledWith(created);
    expect(onClose).not.toHaveBeenCalled();              // ... not only when the user clicks a button
    expect(screen.queryByRole("button", { name: "View My Requests" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onCreated).toHaveBeenCalledTimes(1);          // closing adds no second notification
  });

  it("keeps the host informed even if the user closes with X after submitting", async () => {
    const onCreated = vi.fn();
    const onClose = vi.fn();
    render(<WfhRequestModal onClose={onClose} onCreated={onCreated} />);
    await fillDates();
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    await screen.findByText("Request Submitted!");
    fireEvent.click(screen.getByLabelText("Close"));
    expect(onCreated).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows the API's validation message and stays on the form when the server refuses", async () => {
    post.mockRejectedValue({ response: { data: { message: "You already have a request for these dates." } } });
    const onCreated = vi.fn();
    render(<WfhRequestModal onClose={vi.fn()} onCreated={onCreated} />);
    await fillDates();
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    await waitFor(() => expect(showToast).toHaveBeenCalledWith("You already have a request for these dates.", "error"));
    expect(onCreated).not.toHaveBeenCalled();
    expect(screen.queryByText("Request Submitted!")).toBeNull();
    expect(screen.getByRole("button", { name: "Submit Request" })).toBeTruthy();   // still usable: the user can fix and retry
  });

  it("keeps the refusal on screen in the dialog, saying where the existing requests are (a toast alone disappears)", async () => {
    post.mockRejectedValue({ response: { data: { message: "You already have a work-from-home request for the selected date(s)." } } });
    render(<WfhRequestModal onClose={vi.fn()} onCreated={vi.fn()} />);
    await fillDates();
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("You already have a work-from-home request for the selected date(s).");
    expect(alert.textContent).toContain("Attendance requests");
    expect(alert.textContent).toContain("Requests");
  });

  it("clears that message on the next attempt, and a successful retry shows the success screen", async () => {
    post.mockRejectedValueOnce({ response: { data: { message: "Overlaps an existing request." } } });
    render(<WfhRequestModal onClose={vi.fn()} onCreated={vi.fn()} />);
    await fillDates();
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));   // second try succeeds (default mock)
    expect(await screen.findByText("Request Submitted!")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("calls Close from the dialog header", () => {
    const onClose = vi.fn();
    render(<WfhRequestModal onClose={onClose} onCreated={vi.fn()} />);
    fireEvent.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("RequestWfhForm on the standalone page (no new props)", () => {
  it("keeps its toast-only error behaviour: no inline alert is added to the page", async () => {
    post.mockRejectedValue({ response: { data: { message: "You already have a request for these dates." } } });
    render(<RequestWfhForm onSubmitted={vi.fn()} />);
    await fillDates();
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    await waitFor(() => expect(showToast).toHaveBeenCalledWith("You already have a request for these dates.", "error"));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("still ends on 'View My Requests', which calls onSubmitted", async () => {
    const onSubmitted = vi.fn();
    render(<RequestWfhForm onSubmitted={onSubmitted} />);
    await fillDates();
    fireEvent.click(screen.getByRole("button", { name: "Submit Request" }));
    await screen.findByText("Request Submitted!");
    expect(screen.queryByRole("button", { name: "Done" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "View My Requests" }));
    expect(onSubmitted).toHaveBeenCalledTimes(1);
  });
});
