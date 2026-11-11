// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import ImportJobPanel from "./ImportJobPanel";
import ImportRecentJobs from "./ImportRecentJobs";
import type { ImportJobProgress } from "@/types/employeeImport";

const job = (over: Partial<ImportJobProgress> = {}, invites: Partial<ImportJobProgress["invitations"]> = {}): ImportJobProgress => ({
  job_id: "job-1", status: "completed", is_active: false, file_name: "staff.xlsx", total_rows: 13, processed_rows: 13, created: 13, failed_rows: 0, percent: 100,
  cancel_requested: false, failure_code: "", created_at: null, started_at: null, finished_at: null,
  invitations: { held: false, total: 13, pending: 0, processing: 0, sent: 13, skipped: 0, failed: 0, ...invites }, invitation_failures: [], ...over,
});

const handlers = () => ({ onCancel: vi.fn(), onRetryEmails: vi.fn(), onDownloadErrors: vi.fn() });
const mount = (j: ImportJobProgress, isActing = false) => {
  const h = handlers();
  render(<ImportJobPanel job={j} isActing={isActing} {...h} />);
  return h;
};
const tiles = (testId: string) => within(screen.getByTestId(testId)).getAllByText(/./).map(node => node.textContent);

afterEach(cleanup);

describe("ImportJobPanel", () => {
  it("shows total, processed, created and failed rows while running, with a cancel button", () => {
    const h = mount(job({ status: "running", is_active: true, processed_rows: 5, created: 4, failed_rows: 1, percent: 38 }, { total: 4, sent: 0, pending: 4 }));
    expect(screen.getByTestId("job-headline").textContent).toMatch(/Creating employees: 5 of 13 rows processed, 4 created, 1 row failed/);
    expect(tiles("employee-tiles")).toEqual(["13", "Total rows", "5", "Processed", "4", "Employees created", "1", "Rows failed"]);
    fireEvent.click(screen.getByRole("button", { name: /Cancel import/ }));
    expect(h.onCancel).toHaveBeenCalledTimes(1);
  });

  it("keeps EMPLOYEE CREATION and EMAIL DELIVERY apart: employees created, emails still waiting", () => {
    mount(job({}, { sent: 0, pending: 13 }));
    expect(screen.getByTestId("job-headline").textContent).toMatch(/13 employees created\./);
    expect(tiles("email-tiles")).toEqual(["13", "Waiting", "0", "Sent", "0", "Failed"]);
    expect(screen.getByTestId("email-headline").textContent).toBe("Activation emails: 0 sent, 13 waiting, 0 failed.");
    expect(screen.queryByRole("button", { name: /Retry/ })).toBeNull();
  });

  it("is honest that 'sent' is not 'delivered'", () => {
    mount(job());
    expect(screen.getByText(/does not prove the employee's inbox received it/)).toBeTruthy();
  });

  it("offers a retry for failed emails and lists them, while saying the employees exist", () => {
    const h = mount(job({ invitation_failures: [{ row: 3, employee_id: "10000040", reason: "The mail server could not be reached. Use Retry when it is available." }] }, { sent: 12, failed: 1 }));
    expect(screen.getByText(/Row 3: employee 10000040: The mail server could not be reached/)).toBeTruthy();
    expect(screen.getByTestId("email-headline").textContent).toMatch(/The employees exist; retry the failed emails below/);
    fireEvent.click(screen.getByRole("button", { name: /Retry 1 failed email$/ }));
    expect(h.onRetryEmails).toHaveBeenCalledTimes(1);
  });

  it("disables retry and cancel while an action is in progress", () => {
    mount(job({ status: "running", is_active: true }, { failed: 2, sent: 0, total: 2 }), true);
    expect((screen.getByRole("button", { name: /Retry 2 failed emails/ }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /Cancel import/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("offers the error report only when rows failed", () => {
    const h = mount(job({ status: "completed_with_errors", created: 11, failed_rows: 2 }));
    expect(screen.getByTestId("job-headline").textContent).toMatch(/Completed with errors/);
    fireEvent.click(screen.getByRole("button", { name: /Download error report/ }));
    expect(h.onDownloadErrors).toHaveBeenCalledTimes(1);
    cleanup();
    mount(job());
    expect(screen.queryByRole("button", { name: /Download error report/ })).toBeNull();
  });

  it("explains a hold by an administrator instead of implying emails are on their way", () => {
    mount(job({}, { held: true, sent: 0, pending: 13 }));
    expect(screen.getByTestId("email-headline").textContent).toMatch(/switched off by an administrator/);
  });

  it("shows no action buttons for a clean, finished import", () => {
    mount(job());
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("caps a long list of failures", () => {
    const failures = Array.from({ length: 25 }, (_, index) => ({ row: index + 2, employee_id: `E${index}`, reason: "x" }));
    mount(job({ invitation_failures: failures }, { failed: 25, sent: 0, total: 25 }));
    expect(screen.getByText(/…and 5 more\./)).toBeTruthy();
  });
});

describe("ImportRecentJobs", () => {
  it("lists recent imports with their counts and opens one on request", () => {
    const onOpen = vi.fn();
    render(<ImportRecentJobs jobs={[job({ file_name: "may.xlsx" }, { sent: 12, failed: 1 })]} onOpen={onOpen} />);
    expect(screen.getByText(/may\.xlsx · Completed · 13 created · emails 12 sent, 1 failed/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "View" }));
    expect(onOpen).toHaveBeenCalledWith("job-1");
  });

  it("renders nothing when there are none", () => {
    const { container } = render(<ImportRecentJobs jobs={[]} onOpen={vi.fn()} />);
    expect(container.innerHTML).toBe("");
  });
});
