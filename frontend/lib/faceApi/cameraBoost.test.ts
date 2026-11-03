import { describe, expect, it } from "vitest";
import {
  BOOST_MAX_FRACTION, BOOST_MIN_GAP, TARGET_FACE_LUMINANCE, boostLimit, nextBoostValue, pickBoostControl,
  type RangeCaps,
} from "./cameraBoost";

const RANGE: RangeCaps = { min: -4, max: 4 }; // 8 wide: a step is 0.8, the limit is -4 + 8 * 0.85 = 2.8

describe("pickBoostControl", () => {
  it("prefers exposureCompensation over brightness", () => {
    const picked = pickBoostControl({ exposureCompensation: RANGE, brightness: { min: 0, max: 255 } });
    expect(picked?.control).toBe("exposureCompensation");
  });

  it("falls back to brightness when only that is available", () => {
    expect(pickBoostControl({ brightness: { min: 0, max: 255 } })?.control).toBe("brightness");
  });

  it("returns null when the camera exposes neither control, or the range is unusable", () => {
    expect(pickBoostControl(undefined)).toBeNull();
    expect(pickBoostControl({})).toBeNull();
    expect(pickBoostControl({ exposureCompensation: { min: 1, max: 1 } })).toBeNull();
    expect(pickBoostControl({ brightness: { min: Number.NaN, max: 3 } })).toBeNull();
  });
});

describe("nextBoostValue", () => {
  it("does nothing once the face is bright enough", () => {
    expect(nextBoostValue(0, RANGE, TARGET_FACE_LUMINANCE - BOOST_MIN_GAP)).toBeNull();
    expect(nextBoostValue(0, RANGE, 200)).toBeNull();
  });

  it("raises the value by 10% of the range per step when the face is dim", () => {
    expect(nextBoostValue(0, RANGE, 40)).toBeCloseTo(0.8, 5);
  });

  it("stops at 85% of the range and never goes past it", () => {
    let value = RANGE.min;
    let steps = 0;
    for (let next = nextBoostValue(value, RANGE, 30); next !== null; next = nextBoostValue(value, RANGE, 30)) {
      expect(next).toBeGreaterThan(value);
      expect(next).toBeLessThanOrEqual(boostLimit(RANGE) + 1e-9);
      value = next;
      steps += 1;
      expect(steps).toBeLessThan(50); // always terminates
    }
    expect(value).toBeCloseTo(boostLimit(RANGE), 5);
    expect(boostLimit(RANGE)).toBeCloseTo(RANGE.min + (RANGE.max - RANGE.min) * BOOST_MAX_FRACTION, 5);
    // at the limit, a still-dim face asks for nothing more
    expect(nextBoostValue(value, RANGE, 30)).toBeNull();
  });

  it("snaps to the control's own step size when it declares one", () => {
    const stepped: RangeCaps = { min: 0, max: 10, step: 0.5 };
    const next = nextBoostValue(0, stepped, 30);
    expect(next).toBe(1); // 10% of 10 = 1, already a multiple of 0.5
    const coarse: RangeCaps = { min: 0, max: 10, step: 3 };
    expect(nextBoostValue(0, coarse, 30)).toBe(3); // 1 snaps up to the next multiple of 3
  });
});
