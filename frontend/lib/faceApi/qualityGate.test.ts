import { describe, expect, it } from "vitest";
import {
  assessFrameQuality, selectFailureMessage, classifyDetectedFaceCount,
  MULTIPLE_FACES_MESSAGE, EYE_OCCLUSION_MESSAGE,
  type FrameQualityMetrics,
} from "./qualityGate";

// assessFrameQuality's own pass/fail behavior (each of its 6 checks caught
// individually, one reason apiece) is already covered by the plain-Node
// script at __tests__/qualityGate.verify.ts (run via `npx tsx`, per its own
// header) — not duplicated here. This file covers what's new in this phase:
// that each of those 6 reasons (plus the two new capture-time messages) is
// genuinely distinct text, and that selectFailureMessage — the function
// useFaceLivenessCapture.ts now uses instead of discarding reasons — routes
// a sequence of per-attempt reasons to the correct final message.
const GOOD_METRICS: FrameQualityMetrics = {
  detectionScore: 0.95, faceWidthRatio: 0.4, frontality: 0.95, meanLuminance: 130,
};

function reasonFor(overrides: Partial<FrameQualityMetrics>): string {
  const result = assessFrameQuality({ ...GOOD_METRICS, ...overrides });
  expect(result.reasons).toHaveLength(1);
  return result.reasons[0];
}

describe("assessFrameQuality reasons are genuinely distinct per cause", () => {
  it("produces 6 non-empty, pairwise-distinct messages, one per failure mode", () => {
    const messages = [
      reasonFor({ detectionScore: 0.5 }),   // low confidence
      reasonFor({ faceWidthRatio: 0.05 }),  // too far
      reasonFor({ faceWidthRatio: 0.9 }),   // too close
      reasonFor({ frontality: 0.3 }),       // not frontal
      reasonFor({ meanLuminance: 20 }),     // too dark
      reasonFor({ meanLuminance: 250 }),    // too bright
    ];
    for (const message of messages) expect(message.length).toBeGreaterThan(0);
    expect(new Set(messages).size).toBe(messages.length);
  });

  it("keeps the two lighting messages distinct from each other and from a non-lighting cause", () => {
    const tooDark = reasonFor({ meanLuminance: 20 });
    const tooBright = reasonFor({ meanLuminance: 250 });
    const notFrontal = reasonFor({ frontality: 0.3 });
    expect(tooDark).not.toBe(tooBright);
    expect(tooDark).not.toBe(notFrontal);
    expect(tooBright).not.toBe(notFrontal);
  });
});

describe("selectFailureMessage", () => {
  it("returns null when no attempt ever produced a specific reason (e.g. no face ever detected)", () => {
    expect(selectFailureMessage([[], [], []])).toBeNull();
  });

  it("returns null for an empty attempt sequence", () => {
    expect(selectFailureMessage([])).toBeNull();
  });

  it("returns the sole reason when only one attempt carried one", () => {
    const reason = reasonFor({ meanLuminance: 20 });
    expect(selectFailureMessage([[], [reason], []])).toBe(reason);
  });

  it("prefers the most RECENT specific reason over an earlier one", () => {
    const tooDark = reasonFor({ meanLuminance: 20 });
    const notFrontal = reasonFor({ frontality: 0.3 });
    // Attempt order: dark, then no-face, then not-frontal — the frontality
    // reason is the most recent read of conditions and should win, not the
    // earlier lighting reason.
    expect(selectFailureMessage([[tooDark], [], [notFrontal]])).toBe(notFrontal);
  });

  it("routes a persistent multiple-faces condition to MULTIPLE_FACES_MESSAGE", () => {
    expect(selectFailureMessage([[MULTIPLE_FACES_MESSAGE], [MULTIPLE_FACES_MESSAGE]])).toBe(MULTIPLE_FACES_MESSAGE);
  });

  it("routes a persistent suspected occlusion to EYE_OCCLUSION_MESSAGE", () => {
    expect(selectFailureMessage([[EYE_OCCLUSION_MESSAGE]])).toBe(EYE_OCCLUSION_MESSAGE);
  });

  it("self-heals a transient multi-face blip that clears on a later attempt", () => {
    // Someone walked through the background on one attempt, then left —
    // the later, clean-but-still-too-dark attempt should win instead of the
    // transient multi-face one, since it's the more recent read.
    const tooDark = reasonFor({ meanLuminance: 20 });
    expect(selectFailureMessage([[MULTIPLE_FACES_MESSAGE], [tooDark]])).toBe(tooDark);
  });
});

describe("classifyDetectedFaceCount", () => {
  it("classifies zero detections as 'none' (no face this attempt — silently retried)", () => {
    expect(classifyDetectedFaceCount(0)).toBe("none");
  });

  it("classifies exactly one detection as 'single' (proceeds to the quality gate as before)", () => {
    expect(classifyDetectedFaceCount(1)).toBe("single");
  });

  it("classifies more than one detection as 'multiple', for 2, 3, and a larger crowd alike", () => {
    expect(classifyDetectedFaceCount(2)).toBe("multiple");
    expect(classifyDetectedFaceCount(3)).toBe("multiple");
    expect(classifyDetectedFaceCount(10)).toBe("multiple");
  });

  it("never classifies a single-face fixture (count 1) as 'multiple' — no false-trigger on the existing single-face path", () => {
    expect(classifyDetectedFaceCount(1)).not.toBe("multiple");
  });
});

describe("MULTIPLE_FACES_MESSAGE and EYE_OCCLUSION_MESSAGE", () => {
  it("are non-empty and distinct from each other and from every quality-gate reason", () => {
    expect(MULTIPLE_FACES_MESSAGE.length).toBeGreaterThan(0);
    expect(EYE_OCCLUSION_MESSAGE.length).toBeGreaterThan(0);
    expect(MULTIPLE_FACES_MESSAGE).not.toBe(EYE_OCCLUSION_MESSAGE);
    const gateReason = reasonFor({ meanLuminance: 20 });
    expect(MULTIPLE_FACES_MESSAGE).not.toBe(gateReason);
    expect(EYE_OCCLUSION_MESSAGE).not.toBe(gateReason);
  });
});
