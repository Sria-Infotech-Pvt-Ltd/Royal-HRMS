import { afterEach, describe, expect, it, vi } from "vitest";
import {
  formatLockoutCountdown, loadLockoutUntil, lockoutUntilFromError, saveLockoutUntil, secondsRemaining,
} from "./lockout";

describe("formatLockoutCountdown", () => {
  it("formats as mm:ss", () => {
    expect(formatLockoutCountdown(0)).toBe("00:00");
    expect(formatLockoutCountdown(5)).toBe("00:05");
    expect(formatLockoutCountdown(65)).toBe("01:05");
    expect(formatLockoutCountdown(900)).toBe("15:00");
    expect(formatLockoutCountdown(901)).toBe("15:01");
  });

  it("rounds a fraction up and never goes negative", () => {
    expect(formatLockoutCountdown(59.2)).toBe("01:00");
    expect(formatLockoutCountdown(-3)).toBe("00:00");
  });
});

describe("lockoutUntilFromError", () => {
  const NOW = 1_700_000_000_000;

  it("turns a lockout response into an end time", () => {
    expect(lockoutUntilFromError({ blocked: true, retry_after_seconds: 120 }, NOW)).toBe(NOW + 120_000);
    expect(lockoutUntilFromError({ blocked: true, retry_after_seconds: 0.4 }, NOW)).toBe(NOW + 1000);
  });

  it("ignores anything that is not a lockout", () => {
    expect(lockoutUntilFromError(undefined, NOW)).toBeNull();
    expect(lockoutUntilFromError(null, NOW)).toBeNull();
    expect(lockoutUntilFromError({}, NOW)).toBeNull();
    expect(lockoutUntilFromError({ blocked: false, retry_after_seconds: 60 }, NOW)).toBeNull();
    expect(lockoutUntilFromError({ blocked: true }, NOW)).toBeNull();
    expect(lockoutUntilFromError({ blocked: true, retry_after_seconds: null }, NOW)).toBeNull();
    expect(lockoutUntilFromError({ blocked: true, retry_after_seconds: "60" }, NOW)).toBeNull();
    expect(lockoutUntilFromError({ blocked: true, retry_after_seconds: -5 }, NOW)).toBeNull();
    expect(lockoutUntilFromError({ blocked: true, retry_after_seconds: Number.NaN }, NOW)).toBeNull();
  });
});

describe("secondsRemaining", () => {
  it("counts down in whole seconds, rounding up, and stops at zero", () => {
    expect(secondsRemaining(10_000, 4_500)).toBe(6);
    expect(secondsRemaining(10_000, 9_999)).toBe(1);
    expect(secondsRemaining(10_000, 10_000)).toBe(0);
    expect(secondsRemaining(10_000, 20_000)).toBe(0);
    expect(secondsRemaining(null, 1)).toBe(0);
  });
});

describe("sessionStorage persistence", () => {
  afterEach(() => vi.unstubAllGlobals());

  function stubStorage(initial: Record<string, string> = {}) {
    const store = { ...initial };
    vi.stubGlobal("window", {
      sessionStorage: {
        getItem: (k: string) => (k in store ? store[k] : null),
        setItem: (k: string, v: string) => { store[k] = v; },
        removeItem: (k: string) => { delete store[k]; },
      },
    });
    return store;
  }

  it("saves and restores a lockout that has not ended yet", () => {
    stubStorage();
    const until = Date.now() + 60_000;
    saveLockoutUntil(until);
    expect(loadLockoutUntil()).toBe(until);
  });

  it("drops one that has already ended, and can be cleared", () => {
    const store = stubStorage();
    saveLockoutUntil(Date.now() - 1000);
    expect(loadLockoutUntil()).toBeNull();
    saveLockoutUntil(Date.now() + 60_000);
    saveLockoutUntil(null);
    expect(Object.keys(store)).toHaveLength(0);
  });

  it("ignores garbage in storage", () => {
    stubStorage({ aira_face_lockout_until: "not-a-number" });
    expect(loadLockoutUntil()).toBeNull();
  });

  it("works without any storage (SSR) and when storage throws", () => {
    expect(loadLockoutUntil()).toBeNull(); // node: no window at all
    expect(() => saveLockoutUntil(Date.now() + 1000)).not.toThrow();
    vi.stubGlobal("window", { sessionStorage: { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); }, removeItem: () => { throw new Error("blocked"); } } });
    expect(loadLockoutUntil()).toBeNull();
    expect(() => saveLockoutUntil(Date.now() + 1000)).not.toThrow();
    expect(() => saveLockoutUntil(null)).not.toThrow();
  });
});
