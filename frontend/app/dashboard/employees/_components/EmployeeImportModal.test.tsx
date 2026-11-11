// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import type { ImportJobProgress, ImportPreview } from "@/types/employeeImport";

// The REAL modal + REAL useEmployeeImport + REAL panel; only the network, the downloader and the generic Modal shell are replaced.
const get = vi.fn();
const post = vi.fn();
vi.mock("@/lib/clientApi", () => ({
  default: { get: (...args: unknown[]) => get(...args), post: (...args: unknown[]) => post(...args) },
  isSessionKnownExpired: () => false,
}));
vi.mock("@/lib/downloadFile", () => ({ downloadBlobFile: vi.fn(async () => ({ success: true })) }));
vi.mock("@/components/Modal", () => ({
  default: ({ title, children, footer }: { title: React.ReactNode; children: React.ReactNode; footer?: React.ReactNode }) => (
    <div role="dialog"><div>{title}</div><div>{children}</div><div data-testid="footer">{footer}</div></div>
  ),
}));

import EmployeeImportModal from "./EmployeeImportModal";

const envelope = <T,>(data: T) => ({ data: { status: "success", message: "", data } });
const job = (over: Partial<ImportJobProgress> = {}, invites: Partial<ImportJobProgress["invitations"]> = {}): ImportJobProgress => ({
  job_id: "job-1", status: "running", is_active: true, file_name: "staff.xlsx", total_rows: 3, processed_rows: 1, created: 1, failed_rows: 0, percent: 33,
  cancel_requested: false, failure_code: "", created_at: null, started_at: null, finished_at: null,
  invitations: { held: false, total: 1, pending: 1, processing: 0, sent: 0, skipped: 0, failed: 0, ...invites }, invitation_failures: [], ...over,
});
const preview: ImportPreview = {
  batch_id: "b-1", file_hash: "h-1", can_import: true, allowed_branches: ["Kondapur"],
  summary: { total: 3, valid: 3, invalid: 0, duplicate: 0 }, rows: [],
};

let jobs: ImportJobProgress[];
beforeEach(() => {
  vi.useFakeTimers();
  get.mockReset(); post.mockReset();
  jobs = [];
  get.mockImplementation(async (url: string) => (url === API.employees.importJobs ? envelope({ jobs }) : envelope(jobs[0] ?? job())));
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

async function mount(onSuccess = vi.fn(), onClose = vi.fn()) {
  render(<EmployeeImportModal onClose={onClose} onSuccess={onSuccess} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return { onSuccess, onClose };
}

describe("EmployeeImportModal", () => {
  it("keeps the template download and the file chooser on the first step", async () => {
    await mount();
    expect(screen.getByRole("button", { name: /Download template/ })).toBeTruthy();
    expect(screen.getByText(/Click to choose the filled \.xlsx file/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Preview/ })).toBeTruthy();
  });

  it("runs the whole flow: preview, confirm (creates a job, no synchronous commit), then shows live progress", async () => {
    await mount();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File([new Uint8Array([80, 75, 3, 4])], "staff.xlsx");
    await act(async () => { fireEvent.change(input, { target: { files: [file] } }); });
    post.mockResolvedValueOnce(envelope(preview)).mockResolvedValueOnce(envelope(job({ status: "queued", processed_rows: 0, created: 0 })));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /Preview/ })); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByText(/Everything is valid/)).toBeTruthy();

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /Confirm import of 3/ })); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(post.mock.calls[1][0]).toBe(API.employees.importJobs);
    expect(post.mock.calls.map(call => call[0])).not.toContain(API.employees.importCommit);
    expect(screen.getByTestId("import-job-panel")).toBeTruthy();
    expect(screen.getByTestId("job-headline").textContent).toMatch(/Creating employees|queued/i);
    expect(screen.getByText(/1\. Creating employees/)).toBeTruthy();
    expect(screen.getByText(/2\. Activation emails/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Close" })).toBeTruthy();                      // closing is allowed: progress is saved
  });

  it("goes straight to the progress screen when reopened while an import is still running", async () => {
    jobs = [job({ processed_rows: 2, created: 2, percent: 66 })];
    await mount();
    expect(screen.getByTestId("import-job-panel")).toBeTruthy();
    expect(screen.getByTestId("job-headline").textContent).toMatch(/2 of 3 rows processed, 2 created/);
    expect(screen.queryByText(/Click to choose the filled/)).toBeNull();                      // the upload box is hidden while a job is shown
  });

  it("shows retry for failed emails and offers to import another file when finished", async () => {
    jobs = [job({ status: "completed", is_active: false, created: 3, processed_rows: 3, percent: 100, finished_at: new Date().toISOString(),
                  invitation_failures: [{ row: 2, employee_id: "10000041", reason: "The mail server could not be reached." }] },
                { total: 3, sent: 1, pending: 1, failed: 1 })];
    await mount();
    expect(screen.getByRole("button", { name: /Retry 1 failed email/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Import another file/ })).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /Import another file/ })); });
    expect(screen.getByText(/Click to choose the filled \.xlsx file/)).toBeTruthy();
  });

  it("refreshes the employee list once when the import finishes", async () => {
    jobs = [job({ status: "running" })];
    const { onSuccess } = await mount();
    jobs = [job({ status: "completed", is_active: false, created: 3, processed_rows: 3, percent: 100, finished_at: new Date().toISOString() }, { total: 3, sent: 3, pending: 0 })];
    await act(async () => { await vi.advanceTimersByTimeAsync(3500); });
    expect(onSuccess).toHaveBeenCalledTimes(1);
  });
});
