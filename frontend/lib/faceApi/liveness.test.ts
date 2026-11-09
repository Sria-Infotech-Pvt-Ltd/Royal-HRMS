import { describe, expect, it } from "vitest";
import type { FaceLandmarks68 } from "face-api.js";
import { LivenessTracker } from "./liveness";

// Synthetic 68-point landmarks - only the three groups the tracker reads (both eyes and the nose).
// Eye: 30px wide, `lid` px between the upper and lower lid -> EAR = lid / 30 (0.30 open, ~0.07 closed).
// Eyes span x 100-200 (inter-eye width 100px), so a nose shift of 12px is a head-turn ratio of 0.12.
type Pt = { x: number; y: number };
function eye(x0: number, lid: number): Pt[] {
  const w = 30, y = 100;
  return [
    { x: x0, y },                     { x: x0 + w * 0.33, y: y - lid / 2 }, { x: x0 + w * 0.66, y: y - lid / 2 },
    { x: x0 + w, y },                 { x: x0 + w * 0.66, y: y + lid / 2 }, { x: x0 + w * 0.33, y: y + lid / 2 },
  ];
}
function frame(lid: number, noseX: number): FaceLandmarks68 {
  const nose: Pt[] = Array.from({ length: 9 }, (_, i) => ({ x: noseX, y: 120 + i }));
  return {
    getLeftEye: () => eye(100, lid),
    getRightEye: () => eye(170, lid),
    getNose: () => nose,
  } as unknown as FaceLandmarks68;
}

const OPEN = 9, CLOSED = 2, CENTRE = 150;

function feed(tracker: LivenessTracker, frames: Array<[number, number]>) {
  for (const [lid, noseX] of frames) tracker.addSample(frame(lid, noseX));
}
/** Several steady frames so the open-eye and nose baselines exist. */
function settle(tracker: LivenessTracker, n = 12) {
  feed(tracker, Array.from({ length: n }, () => [OPEN, CENTRE] as [number, number]));
}
/** A genuine blink: eyes close for a few frames, then reopen. */
function blink(tracker: LivenessTracker) {
  feed(tracker, [[CLOSED, CENTRE], [CLOSED, CENTRE], [CLOSED, CENTRE], [OPEN, CENTRE], [OPEN, CENTRE]]);
}
/** A genuine head turn: the nose slides 20px sideways (ratio 0.20 > 0.12), then back. */
function turn(tracker: LivenessTracker) {
  feed(tracker, [[OPEN, CENTRE + 10], [OPEN, CENTRE + 20], [OPEN, CENTRE + 10], [OPEN, CENTRE]]);
}

describe("blink_and_turn (registration): BOTH signals are required", () => {
  it("does not pass on a head turn alone", () => {
    const t = new LivenessTracker("blink_and_turn");
    settle(t); turn(t);
    expect(t.getResult().passed).toBe(false);
    expect(t.getProgress()).toEqual({ blink: false, turn: true });
  });

  it("does not pass on a blink alone", () => {
    const t = new LivenessTracker("blink_and_turn");
    settle(t); blink(t);
    expect(t.getResult().passed).toBe(false);
    expect(t.getProgress()).toEqual({ blink: true, turn: false });
  });

  it("passes once both a blink and a head turn have been seen, in either order", () => {
    const a = new LivenessTracker("blink_and_turn");
    settle(a); blink(a); turn(a);
    expect(a.getResult()).toMatchObject({ passed: true, signal: "blink_and_head_turn" });

    const b = new LivenessTracker("blink_and_turn");
    settle(b); turn(b); blink(b);
    expect(b.getResult()).toMatchObject({ passed: true, signal: "blink_and_head_turn" });
  });

  it("is the default mode", () => {
    const t = new LivenessTracker();
    settle(t); turn(t);
    expect(t.getResult().passed).toBe(false);
  });

  it("a tilted still photo (head-turn landmarks, no blink) never passes", () => {
    const t = new LivenessTracker("blink_and_turn");
    settle(t, 20);
    feed(t, Array.from({ length: 30 }, (_, i) => [OPEN, CENTRE + (i % 2 === 0 ? 18 : -18)] as [number, number]));
    expect(t.getProgress().turn).toBe(true);
    expect(t.getResult().passed).toBe(false);
  });
});

describe("turn_only (Punch In / Punch Out)", () => {
  it("passes on a head turn alone", () => {
    const t = new LivenessTracker("turn_only");
    settle(t); turn(t);
    expect(t.getResult()).toMatchObject({ passed: true, signal: "head_turn" });
  });

  it("does not pass on a blink alone", () => {
    const t = new LivenessTracker("turn_only");
    settle(t); blink(t);
    expect(t.getResult().passed).toBe(false);
  });

  it("does not pass with no movement at all", () => {
    const t = new LivenessTracker("turn_only");
    settle(t, 40);
    expect(t.getResult()).toMatchObject({ passed: false, signal: null });
  });

  it("can be switched mode on the fly (setMode)", () => {
    const t = new LivenessTracker("blink_and_turn");
    settle(t); turn(t);
    expect(t.getResult().passed).toBe(false);
    t.setMode("turn_only");
    expect(t.getResult().passed).toBe(true);
  });
});

describe("noise robustness", () => {
  it("one over-wide eye frame does not inflate the open-eye baseline into a false blink", () => {
    const t = new LivenessTracker("blink_and_turn");
    settle(t, 20);
    feed(t, [[40, CENTRE]]); // a single spurious, much-too-open reading
    settle(t, 20);           // ordinary open eyes afterwards
    expect(t.getProgress().blink).toBe(false);
  });

  it("a real blink is still detected after such a spike", () => {
    const t = new LivenessTracker("blink_and_turn");
    settle(t, 20);
    feed(t, [[40, CENTRE]]);
    settle(t, 20);
    blink(t);
    expect(t.getProgress().blink).toBe(true);
  });

  it("the head-turn baseline is the median of the first frames, so one off-centre first frame does not matter", () => {
    const t = new LivenessTracker("turn_only");
    feed(t, [[OPEN, CENTRE + 15], [OPEN, CENTRE], [OPEN, CENTRE], [OPEN, CENTRE], [OPEN, CENTRE]]);
    feed(t, Array.from({ length: 20 }, () => [OPEN, CENTRE] as [number, number]));
    expect(t.getProgress().turn).toBe(false);
  });
});

describe("reset", () => {
  it("clears every observed signal", () => {
    const t = new LivenessTracker("blink_and_turn");
    settle(t); blink(t); turn(t);
    expect(t.getResult().passed).toBe(true);
    t.reset();
    expect(t.getProgress()).toEqual({ blink: false, turn: false });
    expect(t.getResult().passed).toBe(false);
  });

  it("scores stay within 0..1", () => {
    const t = new LivenessTracker("blink_and_turn");
    settle(t); blink(t); turn(t);
    const { score } = t.getResult();
    expect(score).toBeGreaterThanOrEqual(0);
    expect(score).toBeLessThanOrEqual(1);
  });
});
