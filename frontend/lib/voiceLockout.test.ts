// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { loadLockoutUntil, saveLockoutUntil } from "@/lib/faceApi/lockout";
import { activeLockoutSeconds, voiceLockoutNotice } from "./voiceLockout";

beforeEach(() => window.sessionStorage.clear());
afterEach(() => window.sessionStorage.clear());

describe("voiceLockoutNotice", () => {
  it("is the approved wording with an mm:ss countdown", () => {
    expect(voiceLockoutNotice(75)).toBe("Face check locked. Try again in 01:15");
    expect(voiceLockoutNotice(900)).toBe("Face check locked. Try again in 15:00");
    expect(voiceLockoutNotice(5)).toBe("Face check locked. Try again in 00:05");
  });
});

describe("activeLockoutSeconds (shared face lockout storage)", () => {
  it("is 0 when nothing is stored", () => {
    expect(activeLockoutSeconds()).toBe(0);
  });

  it("reads the same storage the web punch button writes, rounding partial seconds up", () => {
    const now = Date.now();
    saveLockoutUntil(now + 90_500);
    expect(activeLockoutSeconds(now)).toBe(91);
    expect(loadLockoutUntil(now)).toBe(now + 90_500);
  });

  it("is 0 once the end time has passed", () => {
    const now = Date.now();
    saveLockoutUntil(now + 1000);
    expect(activeLockoutSeconds(now + 1000)).toBe(0);
    expect(activeLockoutSeconds(now + 5000)).toBe(0);
  });
});
