// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import { useOpenMenu } from "./useOpenMenu";

function pointerCanHover(canHover: boolean) {
  window.matchMedia = vi.fn().mockReturnValue({ matches: canHover }) as unknown as typeof window.matchMedia; // only .matches is read
}

afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("useOpenMenu with a mouse", () => {
  it("opens a menu when the pointer enters it, without a click first", () => {
    pointerCanHover(true);
    const { result } = renderHook(() => useOpenMenu("/dashboard"));
    act(() => result.current.hoverOpen("workforce"));
    expect(result.current.openKey).toBe("workforce");
  });

  it("closes after a short pause when the pointer leaves, but not if it comes back first", () => {
    vi.useFakeTimers();
    pointerCanHover(true);
    const { result } = renderHook(() => useOpenMenu("/dashboard"));
    act(() => result.current.hoverOpen("workforce"));
    act(() => result.current.hoverLeave());
    act(() => { vi.advanceTimersByTime(100); });
    act(() => result.current.hoverOpen("workforce"));   // crossed the gap into the panel
    act(() => { vi.advanceTimersByTime(500); });
    expect(result.current.openKey).toBe("workforce");
    act(() => result.current.hoverLeave());
    act(() => { vi.advanceTimersByTime(500); });
    expect(result.current.openKey).toBeNull();
  });

  it("a mouse click keeps the hovered menu open, a keyboard press toggles it", () => {
    pointerCanHover(true);
    const { result } = renderHook(() => useOpenMenu("/dashboard"));
    act(() => result.current.hoverOpen("workforce"));
    act(() => result.current.press("workforce", false));
    expect(result.current.openKey).toBe("workforce");
    act(() => result.current.press("workforce", true));
    expect(result.current.openKey).toBeNull();
  });
});

describe("useOpenMenu on a touch screen", () => {
  it("ignores hover and opens and closes on tap", () => {
    pointerCanHover(false);
    const { result } = renderHook(() => useOpenMenu("/dashboard"));
    act(() => result.current.hoverOpen("workforce"));
    expect(result.current.openKey).toBeNull();
    act(() => result.current.press("workforce", false));
    expect(result.current.openKey).toBe("workforce");
    act(() => result.current.press("workforce", false));
    expect(result.current.openKey).toBeNull();
  });
});
