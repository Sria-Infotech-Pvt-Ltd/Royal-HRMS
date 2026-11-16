// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import { weekView } from "@/components/timesheet/fixtures";
import type { TimesheetWeekView } from "@/types/timesheet";

const showToast = vi.fn();
const put = vi.fn();
const post = vi.fn();
let fetched: TimesheetWeekView | null = null;
const requestedUrls: string[] = [];

vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => { requestedUrls.push(url ?? ""); return { data: fetched, loading: false, error: null, status: null, refetch: vi.fn() }; },
}));
vi.mock("@/lib/clientApi", () => ({ default: { put: (...args: unknown[]) => put(...args), post: (...args: unknown[]) => post(...args) } }));

import { useTimesheetWeek } from "./useTimesheetWeek";

const WEEK = "2026-11-09";
const rejection = (errors: string[]) => ({ response: { data: { message: "Some hours need fixing.", data: { errors } } } });

beforeEach(() => { fetched = weekView(); requestedUrls.length = 0; showToast.mockReset(); put.mockReset(); post.mockReset(); });
afterEach(() => cleanup());

describe("useTimesheetWeek", () => {
  it("asks for the week's sheet and returns it", () => {
    const { result } = renderHook(() => useTimesheetWeek(WEEK));
    expect(requestedUrls[0]).toBe(API.attendance.timesheets.myWeekView(WEEK));
    expect(result.current.view?.week_start).toBe(WEEK);
  });

  it("never shows the previous week's sheet while another week is loading", () => {
    const { result } = renderHook(() => useTimesheetWeek("2026-11-16"));
    expect(result.current.view).toBeNull();
  });

  it("a save replaces the sheet with the server's answer and says so", async () => {
    put.mockResolvedValue({ data: { data: weekView({ totals: { ...weekView().totals, week: "8.00" } }) } });
    const { result } = renderHook(() => useTimesheetWeek(WEEK));
    let saved = false;
    await act(async () => { saved = await result.current.save({ lines: [] }); });
    expect(saved).toBe(true);
    expect(put).toHaveBeenCalledWith(API.attendance.timesheets.myWeek(WEEK), { lines: [] });
    expect(result.current.view?.totals.week).toBe("8.00");
    expect(showToast).toHaveBeenCalledWith("Timesheet saved.", "success");
    expect(result.current.isSaving).toBe(false);
  });

  it("a rejected save lists every problem, keeps the sheet, and reports failure", async () => {
    put.mockRejectedValue(rejection(["Mon 9 Nov: bad", "Tue 10 Nov: bad"]));
    const { result } = renderHook(() => useTimesheetWeek(WEEK));
    let saved = true;
    await act(async () => { saved = await result.current.save({ lines: [] }); });
    expect(saved).toBe(false);
    expect(result.current.problems).toEqual(["Mon 9 Nov: bad", "Tue 10 Nov: bad"]);
    expect(result.current.view?.week_start).toBe(WEEK);
    expect(showToast).not.toHaveBeenCalled();
    expect(result.current.isSaving).toBe(false);
  });

  it("a network failure gives a plain fallback message", async () => {
    put.mockRejectedValue(new Error("network"));
    const { result } = renderHook(() => useTimesheetWeek(WEEK));
    await act(async () => { await result.current.save({ lines: [] }); });
    expect(result.current.problems).toEqual(["Could not save the timesheet."]);
  });

  it("submit posts to the week's submit address and shows the locked sheet", async () => {
    post.mockResolvedValue({ data: { data: weekView({ status: "submitted", is_editable: false }) } });
    const { result } = renderHook(() => useTimesheetWeek(WEEK));
    await act(async () => { await result.current.submit(); });
    expect(post).toHaveBeenCalledWith(API.attendance.timesheets.mySubmit(WEEK), {});
    expect(result.current.view?.status).toBe("submitted");
    expect(showToast).toHaveBeenCalledWith("Timesheet submitted for approval.", "success");
  });

  it("a refused submit keeps the editable sheet and lists why", async () => {
    post.mockRejectedValue(rejection(["Enter some hours before submitting."]));
    const { result } = renderHook(() => useTimesheetWeek(WEEK));
    let submitted = true;
    await act(async () => { submitted = await result.current.submit(); });
    expect(submitted).toBe(false);
    expect(result.current.problems).toEqual(["Enter some hours before submitting."]);
    expect(result.current.view?.is_editable).toBe(true);
  });

  it("clears old problems at the start of the next attempt", async () => {
    put.mockRejectedValueOnce(rejection(["bad"])).mockResolvedValueOnce({ data: { data: weekView() } });
    const { result } = renderHook(() => useTimesheetWeek(WEEK));
    await act(async () => { await result.current.save({ lines: [] }); });
    expect(result.current.problems).toHaveLength(1);
    await act(async () => { await result.current.save({ lines: [] }); });
    expect(result.current.problems).toEqual([]);
  });

  it("an answer for one week is not shown under another", async () => {
    put.mockResolvedValue({ data: { data: weekView({ totals: { ...weekView().totals, week: "8.00" } }) } });
    const { result, rerender } = renderHook(({ week }) => useTimesheetWeek(week), { initialProps: { week: WEEK } });
    await act(async () => { await result.current.save({ lines: [] }); });
    fetched = weekView({ week_start: "2026-11-16", week_end: "2026-11-22" });
    rerender({ week: "2026-11-16" });
    expect(result.current.view?.week_start).toBe("2026-11-16");
    expect(result.current.view?.totals.week).toBe("0.00");
  });
});
