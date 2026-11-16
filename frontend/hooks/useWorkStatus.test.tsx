// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import type { WorkStatusResponse } from "@/types/workStatus";
import { SYNC_PENDING_REFETCH_DELAY_MS } from "./useDelayedRefetchOnce";

// The REAL useWorkStatus + REAL useDelayedRefetchOnce; only the data fetching under them is replaced.
const refetch = vi.fn();
let data: Partial<WorkStatusResponse> | null = null;
const useFetchSpy = vi.fn();
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string) => { useFetchSpy(url); return { data, loading: false, error: null, status: null, refetch }; },
}));

import { useWorkStatus } from "./useWorkStatus";

beforeEach(() => { vi.useFakeTimers(); refetch.mockReset(); useFetchSpy.mockReset(); data = null; });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const advance = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });

describe("useWorkStatus", () => {
  it("asks for the signed-in employee's own work status by default", () => {
    renderHook(() => useWorkStatus());
    expect(useFetchSpy).toHaveBeenCalledWith("/work-status/me/?page=1");
  });

  it("asks for another employee's when given one", () => {
    renderHook(() => useWorkStatus("EMP00021", 2));
    expect(useFetchSpy).toHaveBeenCalledWith("/work-status/EMP00021/?page=2");
  });

  it("refetches once, after the delay, when the server says a background sync is pending", () => {
    data = { sync_pending: true, current: [] };
    renderHook(() => useWorkStatus());
    advance(SYNC_PENDING_REFETCH_DELAY_MS - 1);
    expect(refetch).not.toHaveBeenCalled();
    advance(1);
    expect(refetch).toHaveBeenCalledTimes(1);
    advance(10 * 60 * 1000);
    expect(refetch).toHaveBeenCalledTimes(1);   // and never again: no polling
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each([
    ["false", { sync_pending: false }],
    ["absent (an older server)", {}],
  ])("does not refetch when sync_pending is %s", (_label, body) => {
    data = body;
    renderHook(() => useWorkStatus());
    expect(vi.getTimerCount()).toBe(0);
    advance(10 * 60 * 1000);
    expect(refetch).not.toHaveBeenCalled();
  });

  it("does nothing while the first response has not arrived", () => {
    data = null;
    renderHook(() => useWorkStatus());
    advance(10 * 60 * 1000);
    expect(refetch).not.toHaveBeenCalled();
  });
});
