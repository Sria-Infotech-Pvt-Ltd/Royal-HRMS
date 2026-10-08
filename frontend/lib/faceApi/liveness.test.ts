import { describe, expect, it } from "vitest";
import type { FaceLandmarks68 } from "face-api.js";
import { LivenessTracker } from "./liveness";

// Synthetic landmarks in dlib's point order. EAR = eyeHeight / eyeWidth(30),
// so height 9 → EAR 0.30 (open) and height 2 → EAR ~0.07 (closed).
type Pt = { x: number; y: number };

function eye(offsetX: number, height: number): Pt[] {
  const h = height / 2;
  return [
    { x: offsetX,      y: 0 },
    { x: offsetX + 10, y: -h },
    { x: offsetX + 20, y: -h },
    { x: offsetX + 30, y: 0 },
    { x: offsetX + 20, y: h },
    { x: offsetX + 10, y: h },
  ];
}

function landmarks(opts: { eyeHeight: number; noseX: number }): FaceLandmarks68 {
  const nose: Pt[] = Array.from({ length: 9 }, () => ({ x: 0, y: 0 }));
  nose[3] = { x: opts.noseX, y: 30 };
  return {
    getLeftEye: () => eye(0, opts.eyeHeight),
    getRightEye: () => eye(70, opts.eyeHeight),
    getNose: () => nose,
  } as unknown as FaceLandmarks68;
}

const OPEN = 9;
const CLOSED = 2;
const CENTER = 50;
const TURNED = 50 + 20; // 20px shift / 100px inter-eye width = 0.20 > 0.12 threshold

function feed(tracker: LivenessTracker, frames: Array<{ eyeHeight: number; noseX: number }>) {
  frames.forEach(f => tracker.addSample(landmarks(f)));
}

const steady = (n: number, eyeHeight = OPEN, noseX = CENTER) =>
  Array.from({ length: n }, () => ({ eyeHeight, noseX }));

describe("LivenessTracker — both a blink AND a head turn are required", () => {
  it("passes when a blink and a head turn are both observed", () => {
    const t = new LivenessTracker();
    feed(t, steady(10));
    feed(t, [{ eyeHeight: CLOSED, noseX: CENTER }, { eyeHeight: OPEN, noseX: CENTER }]);
    feed(t, steady(5, OPEN, TURNED));
    expect(t.getResult().passed).toBe(true);
    expect(t.getProgress()).toEqual({ blink: true, turn: true });
  });

  it("fails with a blink only", () => {
    const t = new LivenessTracker();
    feed(t, steady(10));
    feed(t, [{ eyeHeight: CLOSED, noseX: CENTER }, { eyeHeight: OPEN, noseX: CENTER }]);
    feed(t, steady(10));
    const result = t.getResult();
    expect(result.passed).toBe(false);
    expect(result.signal).toBe("blink");
  });

  it("fails with a head turn only (the tilted-photo scenario)", () => {
    const t = new LivenessTracker();
    feed(t, steady(10));
    feed(t, steady(10, OPEN, TURNED));
    const result = t.getResult();
    expect(result.passed).toBe(false);
    expect(result.signal).toBe("head_turn");
  });

  it("fails with no motion at all (a still photo)", () => {
    const t = new LivenessTracker();
    feed(t, steady(60));
    expect(t.getResult().passed).toBe(false);
    expect(t.getProgress()).toEqual({ blink: false, turn: false });
  });

  it("still detects a blink caught in a single sampled frame (slow devices)", () => {
    const t = new LivenessTracker();
    feed(t, steady(8));
    feed(t, [{ eyeHeight: CLOSED, noseX: CENTER }]); // only ONE closed frame was sampled
    feed(t, steady(3));
    expect(t.getProgress().blink).toBe(true);
  });
});

describe("LivenessTracker — robustness of the baselines", () => {
  it("does not read a false blink from one noisy over-wide frame (static-image jitter)", () => {
    const t = new LivenessTracker();
    feed(t, steady(10));
    feed(t, [{ eyeHeight: 15, noseX: CENTER }]); // one spike: EAR 0.50 vs normal 0.30
    feed(t, steady(30));
    expect(t.getProgress().blink).toBe(false);
  });

  it("is not thrown off by a first frame caught mid-motion when judging a head turn", () => {
    const t = new LivenessTracker();
    // Frame 1 is off-centre (settling), the rest hold still at the centre: the
    // median baseline must be the centre, so no turn is reported.
    feed(t, [{ eyeHeight: OPEN, noseX: 62 }]);
    feed(t, steady(30));
    expect(t.getProgress().turn).toBe(false);
  });

  it("reset() clears all progress", () => {
    const t = new LivenessTracker();
    feed(t, steady(10));
    feed(t, [{ eyeHeight: CLOSED, noseX: CENTER }, { eyeHeight: OPEN, noseX: CENTER }]);
    feed(t, steady(5, OPEN, TURNED));
    t.reset();
    expect(t.getProgress()).toEqual({ blink: false, turn: false });
    expect(t.getResult().passed).toBe(false);
  });
});
