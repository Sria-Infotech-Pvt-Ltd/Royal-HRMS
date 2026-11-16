// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import { weekView } from "@/components/timesheet/fixtures";
import type { TimesheetWeekView } from "@/types/timesheet";

const showToast = vi.fn();
const post = vi.fn();
const urls: (string | null)[] = [];
let fetched: TimesheetWeekView | null = null;

vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => { urls.push(url); return { data: url ? fetched : null, loading: false, error: null, status: null, refetch: vi.fn() }; },
}));
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));

import { useTimesheetDecision } from "./useTimesheetDecision";

const rejection = (message: string, errors: string[] = [message]) => ({ response: { data: { message, data: { errors } } } });
const decided = (status: "approved" | "returned") => ({ data: { data: weekView({ status, is_editable: status === "returned", can_decide: false }) } });

beforeEach(() => { fetched = weekView({ status: "submitted", can_decide: true }); urls.length = 0; showToast.mockReset(); post.mockReset(); });
afterEach(() => cleanup());

describe("useTimesheetDecision", () => {
  it("reads the sheet at its own address, and nothing when none is open", () => {
    renderHook(() => useTimesheetDecision("T1", vi.fn()));
    expect(urls[0]).toBe(API.attendance.timesheets.detail("T1"));
    urls.length = 0;
    const { result } = renderHook(() => useTimesheetDecision(null, vi.fn()));
    expect(urls[0]).toBeNull();
    expect(result.current.view).toBeNull();
  });

  it("approve posts to the approve address, shows the new state and tells the list to refresh", async () => {
    post.mockResolvedValue(decided("approved"));
    const onChanged = vi.fn();
    const { result } = renderHook(() => useTimesheetDecision("T1", onChanged));
    let done = false;
    await act(async () => { done = await result.current.approve(); });
    expect(done).toBe(true);
    expect(post).toHaveBeenCalledWith(API.attendance.timesheets.approve("T1"), {});
    expect(result.current.view?.status).toBe("approved");
    expect(showToast).toHaveBeenCalledWith("Timesheet approved.", "success");
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(result.current.isBusy).toBe(false);
  });

  it("send back posts the reason", async () => {
    post.mockResolvedValue(decided("returned"));
    const { result } = renderHook(() => useTimesheetDecision("T1", vi.fn()));
    await act(async () => { await result.current.sendBack("Wrong project"); });
    expect(post).toHaveBeenCalledWith(API.attendance.timesheets.returnBack("T1"), { reason: "Wrong project" });
    expect(result.current.view?.status).toBe("returned");
    expect(showToast).toHaveBeenCalledWith("Timesheet sent back to the employee.", "success");
  });

  it("unlock posts the reason", async () => {
    post.mockResolvedValue(decided("returned"));
    const { result } = renderHook(() => useTimesheetDecision("T1", vi.fn()));
    await act(async () => { await result.current.unlock("Fix billable"); });
    expect(post).toHaveBeenCalledWith(API.attendance.timesheets.unlock("T1"), { reason: "Fix billable" });
    expect(showToast).toHaveBeenCalledWith("Timesheet reopened for correction.", "success");
  });

  it("a refused decision keeps the sheet, reports the server's reason, and does not refresh the list", async () => {
    post.mockRejectedValue(rejection("This timesheet is approved, so it cannot be decided now."));
    const onChanged = vi.fn();
    const { result } = renderHook(() => useTimesheetDecision("T1", onChanged));
    let done = true;
    await act(async () => { done = await result.current.approve(); });
    expect(done).toBe(false);
    expect(result.current.problem).toBe("This timesheet is approved, so it cannot be decided now.");
    expect(result.current.view?.status).toBe("submitted");
    expect(onChanged).not.toHaveBeenCalled();
    expect(showToast).not.toHaveBeenCalled();
    expect(result.current.isBusy).toBe(false);
  });

  it("a network failure gives a plain message, and the next attempt clears it", async () => {
    post.mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce(decided("approved"));
    const { result } = renderHook(() => useTimesheetDecision("T1", vi.fn()));
    await act(async () => { await result.current.approve(); });
    expect(result.current.problem).toBe("That did not go through. Please try again.");
    await act(async () => { await result.current.approve(); });
    expect(result.current.problem).toBe("");
  });

  it("does nothing when no sheet is open", async () => {
    const { result } = renderHook(() => useTimesheetDecision(null, vi.fn()));
    let done = true;
    await act(async () => { done = await result.current.approve(); });
    expect(done).toBe(false);
    expect(post).not.toHaveBeenCalled();
  });

  it("an answer for one sheet is not shown for another", async () => {
    post.mockResolvedValue(decided("approved"));
    const { result, rerender } = renderHook(({ id }) => useTimesheetDecision(id, vi.fn()), { initialProps: { id: "T1" } });
    await act(async () => { await result.current.approve(); });
    rerender({ id: "T2" });
    expect(result.current.view?.status).toBe("submitted");
  });
});
