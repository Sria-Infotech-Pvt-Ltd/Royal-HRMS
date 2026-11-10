// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import type { ImportJobProgress, ImportPreview } from "@/types/employeeImport";

// The REAL hook with only the network replaced. The server answers mirror the real backend's shapes (apps.accounts.services_employee_import_job.job_progress
// and the {status, message, data} envelope); the end-to-end script compares the real server's JSON with these keys.
const get = vi.fn();
const post = vi.fn();
const downloadBlobFile = vi.fn();
vi.mock("@/lib/clientApi", () => ({
  default: { get: (...args: unknown[]) => get(...args), post: (...args: unknown[]) => post(...args) },
  isSessionKnownExpired: () => false,
}));
vi.mock("@/lib/downloadFile", () => ({ downloadBlobFile: (...args: unknown[]) => downloadBlobFile(...args) }));

import { useEmployeeImport } from "./useEmployeeImport";

const envelope = <T,>(data: T) => ({ data: { status: "success", message: "", data } });

const job = (over: Partial<ImportJobProgress> = {}, invites: Partial<ImportJobProgress["invitations"]> = {}): ImportJobProgress => ({
  job_id: "job-1", status: "running", is_active: true, file_name: "staff.xlsx", total_rows: 13, processed_rows: 0, created: 0, failed_rows: 0, percent: 0,
  cancel_requested: false, failure_code: "", created_at: null, started_at: null, finished_at: null,
  invitations: { held: false, total: 0, pending: 0, processing: 0, sent: 0, skipped: 0, failed: 0, ...invites }, invitation_failures: [], ...over,
});
const finishedAt = () => new Date().toISOString();

const preview: ImportPreview = {
  batch_id: "batch-uuid", file_hash: "hash123", can_import: true, allowed_branches: ["Kondapur"], rows: [],
  summary: { total: 13, valid: 13, invalid: 0, duplicate: 0 },
};

let jobsList: ImportJobProgress[];
let jobAnswers: ImportJobProgress[];

function answerGets() {
  get.mockImplementation(async (url: string) => {
    if (url === API.employees.importJobs) return envelope({ jobs: jobsList });
    if (url === API.employees.importJob("job-1")) return envelope(jobAnswers.length > 1 ? jobAnswers.shift() : jobAnswers[0]);
    throw new Error(`unexpected GET ${url}`);
  });
}

function xlsx(name = "staff.xlsx") {
  return new File([new Uint8Array([80, 75, 3, 4])], name);
}

async function startedHook(onCreated = vi.fn()) {
  const hook = renderHook(() => useEmployeeImport(onCreated));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return { ...hook, onCreated };
}

async function previewAndConfirm(hook: Awaited<ReturnType<typeof startedHook>>) {
  post.mockReset();
  post.mockResolvedValueOnce(envelope(preview)).mockResolvedValueOnce(envelope(job({ status: "queued" })));
  act(() => hook.result.current.chooseFile(xlsx()));
  await act(async () => { await hook.result.current.runPreview(); });
  await act(async () => { await hook.result.current.confirmImport(); });
}

beforeEach(() => {
  vi.useFakeTimers();
  get.mockReset(); post.mockReset(); downloadBlobFile.mockReset();
  jobsList = [];
  jobAnswers = [job()];
  answerGets();
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("confirming an import", () => {
  it("creates a BACKGROUND JOB (not the old synchronous commit) with the batch id and file hash, and moves to the job step", async () => {
    const hook = await startedHook();
    post.mockReset();
    post.mockResolvedValueOnce(envelope(preview)).mockResolvedValueOnce(envelope(job({ status: "queued" })));
    act(() => hook.result.current.chooseFile(xlsx()));
    await act(async () => { await hook.result.current.runPreview(); });
    await act(async () => { await hook.result.current.confirmImport(); });

    const [url, form] = post.mock.calls[1] as [string, FormData];
    expect(url).toBe(API.employees.importJobs);
    expect(url).not.toBe(API.employees.importCommit);
    expect(form.get("batch_id")).toBe("batch-uuid");
    expect(form.get("file_hash")).toBe("hash123");
    expect((form.get("file") as File).name).toBe("staff.xlsx");
    expect(hook.result.current.step).toBe("job");
    expect(hook.result.current.job?.job_id).toBe("job-1");
    expect(post.mock.calls.map(call => call[0])).not.toContain(API.employees.importCommit);
  });

  it("shows the server's reason when the import is rejected, and stays on the preview", async () => {
    const hook = await startedHook();
    post.mockReset();
    post.mockResolvedValueOnce(envelope(preview)).mockRejectedValueOnce({ response: { status: 400, data: { message: "2 of 13 rows have errors. No employees will be created." } } });
    act(() => hook.result.current.chooseFile(xlsx()));
    await act(async () => { await hook.result.current.runPreview(); });
    await act(async () => { await hook.result.current.confirmImport(); });
    expect(hook.result.current.error).toBe("2 of 13 rows have errors. No employees will be created.");
    expect(hook.result.current.step).toBe("previewed");
  });

  it("tells the user pressing Confirm again is safe when the connection is lost", async () => {
    const hook = await startedHook();
    post.mockReset();
    post.mockResolvedValueOnce(envelope(preview)).mockRejectedValueOnce(new Error("Network Error"));
    act(() => hook.result.current.chooseFile(xlsx()));
    await act(async () => { await hook.result.current.runPreview(); });
    await act(async () => { await hook.result.current.confirmImport(); });
    expect(hook.result.current.error).toMatch(/Press Confirm again: this import cannot be applied twice/);
  });
});

describe("following the job", () => {
  it("polls every 3 seconds while running, updates the counts, and tells the page once when employees exist", async () => {
    jobAnswers = [job({ processed_rows: 4, created: 4, percent: 30 }), job({ status: "completed", is_active: false, processed_rows: 13, created: 13, percent: 100, finished_at: finishedAt() }, { total: 13, sent: 13 })];
    const hook = await startedHook();
    await previewAndConfirm(hook);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });                       // first poll, at once
    expect(hook.result.current.job?.created).toBe(4);
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });                    // second poll, 3 s later
    expect(hook.result.current.job?.status).toBe("completed");
    expect(hook.onCreated).toHaveBeenCalledTimes(1);
    const callsAfterFinish = get.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });                  // settled: no more polling
    expect(get.mock.calls.length).toBe(callsAfterFinish);
    expect(hook.onCreated).toHaveBeenCalledTimes(1);
  });

  it("keeps checking slowly (every 10 s) while only emails remain, then stops when they are done", async () => {
    jobAnswers = [
      job({ status: "completed", is_active: false, created: 13, processed_rows: 13, percent: 100, finished_at: finishedAt() }, { total: 13, pending: 13 }),
      job({ status: "completed", is_active: false, created: 13, processed_rows: 13, percent: 100, finished_at: finishedAt() }, { total: 13, pending: 5, sent: 8 }),
      job({ status: "completed", is_active: false, created: 13, processed_rows: 13, percent: 100, finished_at: finishedAt() }, { total: 13, sent: 13 }),
    ];
    const hook = await startedHook();
    await previewAndConfirm(hook);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(hook.result.current.job?.invitations.pending).toBe(13);
    await act(async () => { await vi.advanceTimersByTimeAsync(9_000); });
    expect(hook.result.current.job?.invitations.pending).toBe(13);                           // not yet: the slow interval is 10 s
    await act(async () => { await vi.advanceTimersByTimeAsync(1_500); });
    expect(hook.result.current.job?.invitations.sent).toBe(8);
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(hook.result.current.job?.invitations.sent).toBe(13);
    const calls = get.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(get.mock.calls.length).toBe(calls);
  });

  it("does not poll forever when an administrator holds the emails", async () => {
    jobAnswers = [job({ status: "completed", is_active: false, created: 13, finished_at: finishedAt() }, { held: true, total: 13, pending: 13 })];
    const hook = await startedHook();
    await previewAndConfirm(hook);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const calls = get.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(120_000); });
    expect(get.mock.calls.length).toBe(calls);
  });
});

describe("closing and reopening the window", () => {
  it("goes straight back to a job that is still running", async () => {
    jobsList = [job({ status: "running", processed_rows: 5, created: 5 })];
    const hook = await startedHook();
    expect(hook.result.current.step).toBe("job");
    expect(hook.result.current.job?.job_id).toBe("job-1");
  });

  it("goes back to a job that finished minutes ago but whose emails are still being sent", async () => {
    jobsList = [job({ status: "completed", is_active: false, created: 13, finished_at: finishedAt() }, { total: 13, pending: 6, sent: 7 })];
    const hook = await startedHook();
    expect(hook.result.current.step).toBe("job");
  });

  it("does not drag the user back to an old finished import, but lists it under recent imports", async () => {
    jobsList = [job({ status: "completed", is_active: false, created: 13, finished_at: "2020-01-01T00:00:00Z" }, { total: 13, sent: 13 })];
    const hook = await startedHook();
    expect(hook.result.current.step).toBe("start");
    expect(hook.result.current.recent).toHaveLength(1);
    expect(hook.onCreated).not.toHaveBeenCalled();
  });

  it("opens a recent import on request without refreshing the employee list again", async () => {
    jobsList = [job({ status: "completed", is_active: false, created: 13, finished_at: "2020-01-01T00:00:00Z" }, { total: 13, sent: 13 })];
    jobAnswers = [jobsList[0]];
    const hook = await startedHook();
    await act(async () => { await hook.result.current.openJob("job-1"); });
    expect(hook.result.current.step).toBe("job");
    expect(hook.onCreated).not.toHaveBeenCalled();
  });

  it("stops polling when the window is closed", async () => {
    jobsList = [job()];
    jobAnswers = [job({ processed_rows: 1, created: 1 })];
    const hook = await startedHook();
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    hook.unmount();
    const calls = get.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(get.mock.calls.length).toBe(calls);
  });
});

describe("retry, cancel and downloads", () => {
  async function onFinishedJobWithFailedEmails() {
    jobsList = [job({ status: "completed", is_active: false, created: 13, finished_at: finishedAt(), invitation_failures: [{ row: 3, employee_id: "10000040", reason: "The mail server could not be reached." }] },
                { total: 13, sent: 12, failed: 1 })];
    jobAnswers = [jobsList[0]];
    const hook = await startedHook();
    expect(hook.result.current.step).toBe("start");                                          // not dragged back: nothing is in flight
    await act(async () => { await hook.result.current.openJob("job-1"); });                  // opened from "Recent imports"
    expect(hook.result.current.step).toBe("job");
    return hook;
  }

  it("retries ONLY the failed emails: it calls the retry endpoint, never the job-creation endpoint, and refreshes the progress", async () => {
    const hook = await onFinishedJobWithFailedEmails();
    post.mockReset();
    post.mockResolvedValueOnce(envelope({ requeued: 1, dispatched: 1 }));
    jobAnswers = [job({ status: "completed", is_active: false, created: 13, finished_at: finishedAt() }, { total: 13, sent: 12, pending: 1 })];
    await act(async () => { await hook.result.current.retryEmails(); });
    expect(post).toHaveBeenCalledTimes(1);
    expect(post.mock.calls[0][0]).toBe(API.employees.importInvitesRetry("job-1"));
    expect(post.mock.calls.map(call => call[0])).not.toContain(API.employees.importJobs);
    expect(hook.result.current.job?.invitations.pending).toBe(1);
    expect(hook.result.current.job?.created).toBe(13);                                       // nobody was created again
  });

  it("restarts polling after a retry so the new result appears", async () => {
    const hook = await onFinishedJobWithFailedEmails();
    post.mockReset();
    post.mockResolvedValueOnce(envelope({ requeued: 1, dispatched: 1 }));
    jobAnswers = [
      job({ status: "completed", is_active: false, created: 13, finished_at: finishedAt() }, { total: 13, sent: 12, pending: 1 }),
      job({ status: "completed", is_active: false, created: 13, finished_at: finishedAt() }, { total: 13, sent: 13 }),
    ];
    await act(async () => { await hook.result.current.retryEmails(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10_500); });
    expect(hook.result.current.job?.invitations.sent).toBe(13);
  });

  it("shows an error and keeps the job when the retry request fails", async () => {
    const hook = await onFinishedJobWithFailedEmails();
    post.mockReset();
    post.mockRejectedValueOnce({ response: { status: 403, data: { message: "You do not have permission to import employees." } } });
    await act(async () => { await hook.result.current.retryEmails(); });
    expect(hook.result.current.error).toBe("You do not have permission to import employees.");
    expect(hook.result.current.job?.job_id).toBe("job-1");
  });

  it("cancels through the cancel endpoint and shows the stopping state", async () => {
    jobsList = [job({ processed_rows: 3, created: 3 })];
    const hook = await startedHook();
    post.mockReset();
    post.mockResolvedValueOnce(envelope(job({ processed_rows: 3, created: 3, cancel_requested: true })));
    jobAnswers = [job({ processed_rows: 3, created: 3, cancel_requested: true })];
    await act(async () => { await hook.result.current.cancelJob(); });
    expect(post.mock.calls[0][0]).toBe(API.employees.importJobCancel("job-1"));
    expect(hook.result.current.job?.cancel_requested).toBe(true);
  });

  it("downloads the error report of the job, not of the uploaded file", async () => {
    const hook = await onFinishedJobWithFailedEmails();
    downloadBlobFile.mockResolvedValueOnce({ success: true });
    await act(async () => { await hook.result.current.downloadJobErrors(); });
    expect(downloadBlobFile).toHaveBeenCalledWith(API.employees.importJobErrors("job-1"), {}, "employee_import_errors.xlsx");
  });

  it("starting a new import clears the previous one and goes back to the file step", async () => {
    const hook = await onFinishedJobWithFailedEmails();
    act(() => hook.result.current.startNew());
    expect(hook.result.current.step).toBe("start");
    expect(hook.result.current.job).toBeNull();
  });
});
