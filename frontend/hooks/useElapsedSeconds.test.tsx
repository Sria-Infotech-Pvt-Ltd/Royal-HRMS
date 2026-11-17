// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useElapsedSeconds, useRefetchWhileActive } from "./useElapsedSeconds";

const START = new Date("2026-11-17T04:00:00Z").getTime();

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
  vi.setSystemTime(START);
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

function goBackToTab() {
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("useElapsedSeconds", () => {
  it("counts real seconds while running", () => {
    const { result } = renderHook(() => useElapsedSeconds("figures-1", true));
    expect(result.current).toBe(0);
    act(() => { vi.advanceTimersByTime(3000); });
    expect(result.current).toBe(3);
  });

  it("is right after a hidden tab skipped its ticks: the clock moved 65 s but no timer fired", () => {
    const { result } = renderHook(() => useElapsedSeconds("figures-1", true));
    act(() => { vi.setSystemTime(START + 65_000); goBackToTab(); });   // the browser never ran the interval; the real clock did advance
    expect(result.current).toBe(65);
  });

  it("restarts from zero when fresh server figures arrive", () => {
    const { result, rerender } = renderHook(({ token }) => useElapsedSeconds(token, true), { initialProps: { token: "figures-1" } });
    act(() => { vi.advanceTimersByTime(10_000); });
    expect(result.current).toBe(10);
    rerender({ token: "figures-2" });
    expect(result.current).toBe(0);
    act(() => { vi.advanceTimersByTime(2000); });
    expect(result.current).toBe(2);
  });

  it("adds nothing while not running, and nothing that is left over from earlier", () => {
    const { result, rerender } = renderHook(({ running }) => useElapsedSeconds("figures-1", running), { initialProps: { running: true } });
    act(() => { vi.advanceTimersByTime(5000); });
    expect(result.current).toBe(5);
    rerender({ running: false });
    expect(result.current).toBe(0);
  });
});

describe("useRefetchWhileActive", () => {
  it("re-reads the server when the tab is visible again and every five minutes while active", () => {
    const refetch = vi.fn();
    renderHook(() => useRefetchWhileActive(refetch, true));
    expect(refetch).not.toHaveBeenCalled();
    act(() => { goBackToTab(); });
    expect(refetch).toHaveBeenCalledTimes(1);
    act(() => { vi.advanceTimersByTime(5 * 60 * 1000); });
    expect(refetch).toHaveBeenCalledTimes(2);
  });

  it("does nothing while not active", () => {
    const refetch = vi.fn();
    renderHook(() => useRefetchWhileActive(refetch, false));
    act(() => { goBackToTab(); vi.advanceTimersByTime(10 * 60 * 1000); });
    expect(refetch).not.toHaveBeenCalled();
  });
});
