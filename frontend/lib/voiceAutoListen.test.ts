import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAutoListenScheduler, shouldAutoListenAfterSpeaking } from "./voiceAutoListen";

describe("shouldAutoListenAfterSpeaking", () => {
  it("auto-listens for a genuine multi-turn follow-up (awaiting_input, not face-proof)", () => {
    expect(shouldAutoListenAfterSpeaking(true, false)).toBe(true);
  });

  it("does not auto-listen for a final/single-turn response (awaiting_input false)", () => {
    expect(shouldAutoListenAfterSpeaking(false, false)).toBe(false);
  });

  it("does not auto-listen for the face-proof camera turn, even though it's awaiting_input", () => {
    // The next expected input there is a captured face descriptor via
    // FaceVerificationModal, not speech — opening the mic would be wrong.
    expect(shouldAutoListenAfterSpeaking(true, true)).toBe(false);
  });

  it("does not auto-listen when neither flag is set", () => {
    expect(shouldAutoListenAfterSpeaking(false, true)).toBe(false);
  });
});

describe("createAutoListenScheduler", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fires onFire ~1s after schedule() when the token is still current", () => {
    const onFire = vi.fn();
    const scheduler = createAutoListenScheduler(() => 1, onFire, 1000);

    scheduler.schedule(1);
    expect(onFire).not.toHaveBeenCalled();

    vi.advanceTimersByTime(999);
    expect(onFire).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(onFire).toHaveBeenCalledTimes(1);
  });

  it("does not fire for a response superseded by a newer utterance before the delay elapses", () => {
    // Simulates cancelSpeech() bumping the token (e.g. a new command came
    // in) while the 1s wait for the OLD response is still running.
    let currentToken = 1;
    const onFire = vi.fn();
    const scheduler = createAutoListenScheduler(() => currentToken, onFire, 1000);

    scheduler.schedule(1);
    currentToken = 2; // a newer utterance now owns the conversation
    vi.advanceTimersByTime(1000);

    expect(onFire).not.toHaveBeenCalled();
  });

  it("cancel() prevents a pending fire — the manual-start race resolves cleanly", () => {
    // Mirrors what startListening() does on a manual click: cancel any
    // scheduled auto-listen so it can't spuriously reopen the mic later,
    // after the manually-started session has already run its course.
    const onFire = vi.fn();
    const scheduler = createAutoListenScheduler(() => 1, onFire, 1000);

    scheduler.schedule(1);
    vi.advanceTimersByTime(500); // user manually clicks mic partway through the wait
    scheduler.cancel();
    vi.advanceTimersByTime(1000);

    expect(onFire).not.toHaveBeenCalled();
  });

  it("cancel() is a harmless no-op when nothing is scheduled", () => {
    const onFire = vi.fn();
    const scheduler = createAutoListenScheduler(() => 1, onFire, 1000);
    expect(() => scheduler.cancel()).not.toThrow();
    vi.advanceTimersByTime(5000);
    expect(onFire).not.toHaveBeenCalled();
  });

  it("a second schedule() call replaces the first — only the most recent one can fire", () => {
    const onFire = vi.fn();
    const scheduler = createAutoListenScheduler(() => 7, onFire, 1000);

    scheduler.schedule(7);
    vi.advanceTimersByTime(400);
    scheduler.schedule(7); // re-armed, e.g. a fresh onEnd for another turn of the same token
    vi.advanceTimersByTime(600); // total 1000ms since the FIRST schedule, but only 600ms since the second

    expect(onFire).not.toHaveBeenCalled();

    vi.advanceTimersByTime(400); // now 1000ms since the second schedule
    expect(onFire).toHaveBeenCalledTimes(1);
  });

  it("reads getCurrentToken only at fire time, not at schedule time", () => {
    // If the token changed and then changed BACK to the original value by
    // the time the delay elapses, this is indistinguishable from "never
    // superseded" from the scheduler's point of view — documenting that as
    // the actual (acceptable) behavior, not asserting a stricter guarantee
    // the implementation doesn't provide.
    let currentToken = 3;
    const onFire = vi.fn();
    const scheduler = createAutoListenScheduler(() => currentToken, onFire, 1000);

    scheduler.schedule(3);
    currentToken = 4;
    currentToken = 3;
    vi.advanceTimersByTime(1000);

    expect(onFire).toHaveBeenCalledTimes(1);
  });
});
