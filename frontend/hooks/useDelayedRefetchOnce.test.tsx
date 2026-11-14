// @vitest-environment jsdom
import { StrictMode, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import { SYNC_PENDING_REFETCH_DELAY_MS, useDelayedRefetchOnce } from "./useDelayedRefetchOnce";

beforeEach(() => vi.useFakeTimers());
afterEach(() => { cleanup(); vi.useRealTimers(); });

const advance = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });

describe("useDelayedRefetchOnce", () => {
  it("does nothing, and schedules nothing, while no job is pending", () => {
    const refetch = vi.fn();
    renderHook(() => useDelayedRefetchOnce(false, refetch));
    expect(vi.getTimerCount()).toBe(0);
    advance(10 * 60 * 1000);
    expect(refetch).not.toHaveBeenCalled();
  });

  it("refetches once, only after the delay", () => {
    const refetch = vi.fn();
    renderHook(() => useDelayedRefetchOnce(true, refetch));
    advance(SYNC_PENDING_REFETCH_DELAY_MS - 1);
    expect(refetch).not.toHaveBeenCalled();
    advance(1);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("is not polling: even if the answer is still 'pending', nothing more is scheduled", () => {
    const refetch = vi.fn();
    const { rerender } = renderHook(({ pending }) => useDelayedRefetchOnce(pending, refetch), { initialProps: { pending: true } });
    advance(SYNC_PENDING_REFETCH_DELAY_MS);
    expect(refetch).toHaveBeenCalledTimes(1);
    rerender({ pending: true });                 // the refetched response still says pending
    expect(vi.getTimerCount()).toBe(0);          // no interval, no further timeout
    advance(10 * 60 * 1000);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("never schedules a second refetch, even if the state flips pending again later", () => {
    const refetch = vi.fn();
    const { rerender } = renderHook(({ pending }) => useDelayedRefetchOnce(pending, refetch), { initialProps: { pending: true } });
    advance(SYNC_PENDING_REFETCH_DELAY_MS);
    rerender({ pending: false });
    rerender({ pending: true });
    expect(vi.getTimerCount()).toBe(0);
    advance(10 * 60 * 1000);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("is cancelled if the page goes away first", () => {
    const refetch = vi.fn();
    const { unmount } = renderHook(() => useDelayedRefetchOnce(true, refetch));
    unmount();
    expect(vi.getTimerCount()).toBe(0);
    advance(60 * 1000);
    expect(refetch).not.toHaveBeenCalled();
  });

  it("stops waiting if the data stops being pending before the delay", () => {
    const refetch = vi.fn();
    const { rerender } = renderHook(({ pending }) => useDelayedRefetchOnce(pending, refetch), { initialProps: { pending: true } });
    rerender({ pending: false });                // e.g. the person changed page and got a settled answer
    advance(SYNC_PENDING_REFETCH_DELAY_MS * 2);
    expect(refetch).not.toHaveBeenCalled();
  });

  it("still refetches exactly once under React strict mode, which runs every effect twice in development", () => {
    const refetch = vi.fn();
    const wrapper = ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode>;
    renderHook(() => useDelayedRefetchOnce(true, refetch), { wrapper });
    advance(SYNC_PENDING_REFETCH_DELAY_MS);
    expect(refetch).toHaveBeenCalledTimes(1);
    advance(10 * 60 * 1000);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("calls the latest refetch without restarting the timer when its identity changes", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = renderHook(({ refetch }) => useDelayedRefetchOnce(true, refetch), { initialProps: { refetch: first } });
    advance(SYNC_PENDING_REFETCH_DELAY_MS - 1000);
    rerender({ refetch: second });               // useFetch builds a new refetch function whenever its URL changes
    advance(1000);                               // the ORIGINAL deadline: the timer was not restarted
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });

  it("honours a custom delay", () => {
    const refetch = vi.fn();
    renderHook(() => useDelayedRefetchOnce(true, refetch, 1500));
    advance(1499);
    expect(refetch).not.toHaveBeenCalled();
    advance(1);
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});
