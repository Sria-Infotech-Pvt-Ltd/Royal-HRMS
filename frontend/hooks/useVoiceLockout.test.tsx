// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { loadLockoutUntil, saveLockoutUntil } from "@/lib/faceApi/lockout";
import { useVoiceLockout } from "./useVoiceLockout";

const STORAGE_KEY = "aira_face_lockout_until"; // the SAME key the manual Punch In/Out button uses

beforeEach(() => {
  vi.useFakeTimers();
  window.sessionStorage.clear();
});
afterEach(() => {
  vi.useRealTimers();
  window.sessionStorage.clear();
});

describe("useVoiceLockout", () => {
  it("is idle (0 seconds, not locked) when nothing is stored", () => {
    const { result } = renderHook(() => useVoiceLockout());
    expect(result.current.lockoutSecondsRemaining).toBe(0);
    expect(result.current.isLockedOut).toBe(false);
  });

  it("recordLockout stores the shared end time and starts the countdown from retry_after_seconds", () => {
    const { result } = renderHook(() => useVoiceLockout());
    let recorded = false;
    act(() => { recorded = result.current.recordLockout({ blocked: true, retry_after_seconds: 90 }); });
    expect(recorded).toBe(true);
    expect(result.current.lockoutSecondsRemaining).toBe(90);
    expect(result.current.isLockedOut).toBe(true);
    expect(window.sessionStorage.getItem(STORAGE_KEY)).not.toBeNull();
    expect(loadLockoutUntil()).toBeGreaterThan(Date.now());
  });

  it("ticks once per second and expires back to 0", () => {
    const { result } = renderHook(() => useVoiceLockout());
    act(() => { result.current.recordLockout({ blocked: true, retry_after_seconds: 3 }); });
    expect(result.current.lockoutSecondsRemaining).toBe(3);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(result.current.lockoutSecondsRemaining).toBe(2);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(result.current.lockoutSecondsRemaining).toBe(1);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(result.current.lockoutSecondsRemaining).toBe(0);
    expect(result.current.isLockedOut).toBe(false);
  });

  it("ignores anything that is not a lockout response", () => {
    const { result } = renderHook(() => useVoiceLockout());
    for (const notALockout of [null, undefined, {}, { blocked: false, retry_after_seconds: 30 },
      { blocked: true }, { blocked: true, retry_after_seconds: 0 }, { awaiting_face_proof: true }]) {
      let recorded = true;
      act(() => { recorded = result.current.recordLockout(notALockout); });
      expect(recorded).toBe(false);
    }
    expect(result.current.lockoutSecondsRemaining).toBe(0);
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("picks up a lockout recorded elsewhere in the tab (the web punch button) on the next tick", () => {
    const { result } = renderHook(() => useVoiceLockout());
    expect(result.current.lockoutSecondsRemaining).toBe(0);
    act(() => { saveLockoutUntil(Date.now() + 45_000); });
    act(() => { vi.advanceTimersByTime(1000); });
    expect(result.current.lockoutSecondsRemaining).toBe(44);
  });

  it("resumes a lockout that was already running when the hook mounts (e.g. after a page change)", () => {
    saveLockoutUntil(Date.now() + 30_000);
    const { result } = renderHook(() => useVoiceLockout());
    expect(result.current.lockoutSecondsRemaining).toBe(30);
  });

  it("stops its timer on unmount", () => {
    const { unmount } = renderHook(() => useVoiceLockout());
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
