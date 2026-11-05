import { describe, expect, it } from "vitest";
import { assessLiveReadiness, READINESS_HINTS, type LiveReadinessInput } from "./readiness";
import { QUALITY_THRESHOLDS } from "./qualityGate";

const GOOD: LiveReadinessInput = {
  faceWidthRatio: 0.4, frontality: 0.95, insideGuide: true, detectionScore: 0.95,
  faceLuminance: 120, frameLuminance: 125,
};

describe("assessLiveReadiness - geometry blocks", () => {
  it("is ready for a well-framed, well-lit face", () => {
    const r = assessLiveReadiness(GOOD);
    expect(r).toMatchObject({ ready: true, code: null, hint: null, lowLight: false, backlit: false });
  });

  it("blocks a face that is too far", () => {
    const r = assessLiveReadiness({ ...GOOD, faceWidthRatio: QUALITY_THRESHOLDS.MIN_FACE_WIDTH_RATIO - 0.01 });
    expect(r.ready).toBe(false);
    expect(r.code).toBe("too_far");
    expect(r.hint).toBe(READINESS_HINTS.too_far);
  });

  it("blocks a face that is too close", () => {
    const r = assessLiveReadiness({ ...GOOD, faceWidthRatio: QUALITY_THRESHOLDS.MAX_FACE_WIDTH_RATIO + 0.01 });
    expect(r.ready).toBe(false);
    expect(r.code).toBe("too_close");
  });

  it("blocks a face outside the dotted guide (off-centre)", () => {
    const r = assessLiveReadiness({ ...GOOD, insideGuide: false });
    expect(r.ready).toBe(false);
    expect(r.code).toBe("not_centered");
  });

  it("blocks a face that is not looking at the camera", () => {
    const r = assessLiveReadiness({ ...GOOD, frontality: QUALITY_THRESHOLDS.MIN_FRONTALITY - 0.05 });
    expect(r.ready).toBe(false);
    expect(r.code).toBe("not_frontal");
  });

  it("does not judge the guide when it is not supplied", () => {
    expect(assessLiveReadiness({ ...GOOD, insideGuide: undefined }).ready).toBe(true);
  });

  it("reports the most important blocking problem first: far, then close, then off-centre, then not frontal", () => {
    const all = { ...GOOD, insideGuide: false, frontality: 0.1 };
    expect(assessLiveReadiness({ ...all, faceWidthRatio: 0.05 }).code).toBe("too_far");
    expect(assessLiveReadiness({ ...all, faceWidthRatio: 0.9 }).code).toBe("too_close");
    expect(assessLiveReadiness({ ...all, faceWidthRatio: 0.4 }).code).toBe("not_centered");
    expect(assessLiveReadiness({ ...all, faceWidthRatio: 0.4, insideGuide: true }).code).toBe("not_frontal");
  });
});

describe("assessLiveReadiness - lighting is advisory and never blocks", () => {
  it("a dark face is ready but hints, and flags lowLight for the fill light", () => {
    const r = assessLiveReadiness({ ...GOOD, faceLuminance: 30, frameLuminance: 35 });
    expect(r.ready).toBe(true);
    expect(r.code).toBe("too_dark");
    expect(r.lowLight).toBe(true);
  });

  it("a backlit face is ready but hints", () => {
    const r = assessLiveReadiness({ ...GOOD, faceLuminance: 80, frameLuminance: 200 });
    expect(r.ready).toBe(true);
    expect(r.code).toBe("backlit");
    expect(r.backlit).toBe(true);
  });

  it("low detector confidence is ready but hints", () => {
    const r = assessLiveReadiness({ ...GOOD, detectionScore: 0.5 });
    expect(r.ready).toBe(true);
    expect(r.code).toBe("low_confidence");
  });

  it("a geometry problem wins over a lighting hint", () => {
    const r = assessLiveReadiness({ ...GOOD, faceWidthRatio: 0.05, faceLuminance: 20, frameLuminance: 20 });
    expect(r.ready).toBe(false);
    expect(r.code).toBe("too_far");
    expect(r.lowLight).toBe(true); // the fill-light cue still works while the person is being moved
  });

  it("makes no lighting claim before luminance has been sampled", () => {
    const r = assessLiveReadiness({ ...GOOD, faceLuminance: null, frameLuminance: null });
    expect(r).toMatchObject({ ready: true, code: null, lowLight: false, backlit: false });
  });
});
