import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { pollWhileSessionLive } from "./pollWhileSessionLive";

function fakeSession() {
  let expired = false;
  const listeners = new Set<() => void>();
  return {
    deps: {
      isExpired: () => expired,
      onExpired: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    },
    expire() { expired = true; },
    announceExpiry() { expired = true; [...listeners].forEach(listener => listener()); },
    listenerCount: () => listeners.size,
  };
}

describe("pollWhileSessionLive", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("polls immediately and then on every interval while the session is alive", () => {
    const session = fakeSession();
    const poll = vi.fn();
    pollWhileSessionLive(poll, 60_000, session.deps);
    expect(poll).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(180_000);
    expect(poll).toHaveBeenCalledTimes(4);
  });

  it("stops polling once the session is known to be expired (the next tick notices)", () => {
    const session = fakeSession();
    const poll = vi.fn();
    pollWhileSessionLive(poll, 60_000, session.deps);
    session.expire();
    vi.advanceTimersByTime(600_000);
    expect(poll).toHaveBeenCalledTimes(1);          // only the first, live poll
  });

  it("stops at once when the session-expired event fires, and unsubscribes", () => {
    const session = fakeSession();
    const poll = vi.fn();
    pollWhileSessionLive(poll, 60_000, session.deps);
    session.announceExpiry();
    vi.advanceTimersByTime(600_000);
    expect(poll).toHaveBeenCalledTimes(1);
    expect(session.listenerCount()).toBe(0);
  });

  it("does not start at all when the session is already expired", () => {
    const session = fakeSession();
    session.expire();
    const poll = vi.fn();
    pollWhileSessionLive(poll, 60_000, session.deps);
    vi.advanceTimersByTime(600_000);
    expect(poll).not.toHaveBeenCalled();
    expect(session.listenerCount()).toBe(0);
  });

  it("the returned cleanup stops polling and unsubscribes", () => {
    const session = fakeSession();
    const poll = vi.fn();
    const stop = pollWhileSessionLive(poll, 60_000, session.deps);
    stop();
    vi.advanceTimersByTime(600_000);
    expect(poll).toHaveBeenCalledTimes(1);
    expect(session.listenerCount()).toBe(0);
  });
});
