import { describe, expect, it } from "vitest";
import { assessLiveReadiness, READINESS_HINTS, type LiveReadinessInput } from "./readiness";

const GOOD: LiveReadinessInput = {
  faceWidthRatio: 0.4, frontality: 0.95, detectionScore: 0.95, faceLuminance: 130, frameLuminance: 125,
};

describe("assessLiveReadiness", () => {
  it("is ready with no hint for a well-framed, well-lit face", () => {
    const r = assessLiveReadiness(GOOD);
    expect(r).toMatchObject({ ready: true, code: null, hint: null, lowLight: false, backlit: false });
  });

  it("blocks and hints on geometry problems, matching the capture gate's thresholds", () => {
    expect(assessLiveReadiness({ ...GOOD, faceWidthRatio: 0.1 })).toMatchObject({ ready: false, code: "too_far" });
    expect(assessLiveReadiness({ ...GOOD, faceWidthRatio: 0.9 })).toMatchObject({ ready: false, code: "too_close" });
    expect(assessLiveReadiness({ ...GOOD, frontality: 0.4 })).toMatchObject({ ready: false, code: "not_frontal" });
  });

  it("only hints (does not block) on lighting and detector confidence", () => {
    const dark = assessLiveReadiness({ ...GOOD, faceLuminance: 30, frameLuminance: 40 });
    expect(dark).toMatchObject({ ready: true, code: "too_dark", lowLight: true });
    const lowConf = assessLiveReadiness({ ...GOOD, detectionScore: 0.6 });
    expect(lowConf).toMatchObject({ ready: true, code: "low_confidence" });
  });

  it("detects backlighting: bright scene, dim face", () => {
    const r = assessLiveReadiness({ ...GOOD, faceLuminance: 80, frameLuminance: 170 });
    expect(r).toMatchObject({ ready: true, code: "backlit", backlit: true });
  });

  it("does not call a bright, evenly lit face backlit", () => {
    expect(assessLiveReadiness({ ...GOOD, faceLuminance: 150, frameLuminance: 200 }).backlit).toBe(false);
  });

  it("does not guess about lighting before luminance has been sampled", () => {
    const r = assessLiveReadiness({ ...GOOD, faceLuminance: null, frameLuminance: null });
    expect(r).toMatchObject({ ready: true, code: null, lowLight: false, backlit: false });
  });

  it("prioritises geometry over lighting hints", () => {
    expect(assessLiveReadiness({ ...GOOD, faceWidthRatio: 0.1, faceLuminance: 20 }).code).toBe("too_far");
  });

  it("every code has a distinct non-empty hint", () => {
    const hints = Object.values(READINESS_HINTS);
    expect(new Set(hints).size).toBe(hints.length);
    hints.forEach(h => expect(h.length).toBeGreaterThan(5));
  });
});
