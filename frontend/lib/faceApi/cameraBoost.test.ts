import { describe, expect, it } from "vitest";
import {
  pickBoostControl, nextBoostValue, boostLimit, TARGET_FACE_LUMINANCE, BOOST_MIN_GAP,
} from "./cameraBoost";

const EXPOSURE = { min: -2, max: 2, step: 0.5 };
const BRIGHTNESS = { min: 0, max: 255, step: 1 };

describe("pickBoostControl", () => {
  it("prefers exposureCompensation, falls back to brightness, else null", () => {
    expect(pickBoostControl({ exposureCompensation: EXPOSURE, brightness: BRIGHTNESS })?.control).toBe("exposureCompensation");
    expect(pickBoostControl({ brightness: BRIGHTNESS })?.control).toBe("brightness");
    expect(pickBoostControl({})).toBeNull();
    expect(pickBoostControl(undefined)).toBeNull();
  });

  it("ignores degenerate ranges", () => {
    expect(pickBoostControl({ exposureCompensation: { min: 1, max: 1 } })).toBeNull();
  });
});

describe("nextBoostValue", () => {
  it("does nothing when the face is already bright enough", () => {
    expect(nextBoostValue(0, EXPOSURE, TARGET_FACE_LUMINANCE)).toBeNull();
    expect(nextBoostValue(0, EXPOSURE, TARGET_FACE_LUMINANCE - BOOST_MIN_GAP)).toBeNull();
  });

  it("raises gradually: small step, snapped to the control's step size", () => {
    const next = nextBoostValue(0, EXPOSURE, 40);
    expect(next).not.toBeNull();
    expect(next!).toBeGreaterThan(0);
    expect(next!).toBeLessThanOrEqual(0.5 + 1e-9); // 10% of a 4-wide range, snapped up to the next 0.5
    expect((next! - EXPOSURE.min) % EXPOSURE.step).toBeCloseTo(0, 6);
  });

  it("walks up step by step and then stops at the safe limit, never reaching the maximum", () => {
    let value = 0;
    let steps = 0;
    for (; steps < 100; steps++) {
      const next = nextBoostValue(value, BRIGHTNESS, 20);
      if (next === null) break;
      expect(next).toBeGreaterThan(value);
      value = next;
    }
    expect(steps).toBeGreaterThan(3);               // gradual, not one jump
    expect(steps).toBeLessThan(100);                // and it terminates
    expect(value).toBeLessThanOrEqual(boostLimit(BRIGHTNESS));
    expect(value).toBeLessThan(BRIGHTNESS.max);
  });

  it("returns null once the limit is reached even if the face is still dim", () => {
    expect(nextBoostValue(boostLimit(EXPOSURE), EXPOSURE, 10)).toBeNull();
  });
});
