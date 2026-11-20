// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ renew: vi.fn(() => Promise.resolve()), expired: vi.fn(() => false) }));
vi.mock("@/lib/clientApi", () => ({ renewLoginIfStale: () => mocks.renew(), isSessionKnownExpired: () => mocks.expired() }));

import { useSessionKeepAlive } from "./useSessionKeepAlive";

function Probe() { useSessionKeepAlive(); return null; }

let visibility: "visible" | "hidden" = "visible";

beforeEach(() => {
  vi.useFakeTimers();
  mocks.renew.mockClear();
  mocks.expired.mockReturnValue(false);
  visibility = "visible";
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => visibility });
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("useSessionKeepAlive", () => {
  it("checks when the app opens and then every minute while the tab is on screen", () => {
    render(<Probe />);
    expect(mocks.renew).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(60_000);
    expect(mocks.renew).toHaveBeenCalledTimes(2);
    vi.advanceTimersByTime(120_000);
    expect(mocks.renew).toHaveBeenCalledTimes(4);
  });

  it("checks the moment the tab comes back into view, the window is focused or the network returns", () => {
    render(<Probe />);
    mocks.renew.mockClear();
    document.dispatchEvent(new Event("visibilitychange"));
    window.dispatchEvent(new Event("focus"));
    window.dispatchEvent(new Event("online"));
    expect(mocks.renew).toHaveBeenCalledTimes(3);
  });

  it("does nothing while the tab is hidden", () => {
    visibility = "hidden";
    render(<Probe />);
    vi.advanceTimersByTime(180_000);
    expect(mocks.renew).not.toHaveBeenCalled();
  });

  it("does nothing once the session is known to be over", () => {
    mocks.expired.mockReturnValue(true);
    render(<Probe />);
    vi.advanceTimersByTime(120_000);
    expect(mocks.renew).not.toHaveBeenCalled();
  });

  it("stops everything when the page goes away", () => {
    const { unmount } = render(<Probe />);
    unmount();
    mocks.renew.mockClear();
    vi.advanceTimersByTime(180_000);
    window.dispatchEvent(new Event("focus"));
    expect(mocks.renew).not.toHaveBeenCalled();
  });
});
