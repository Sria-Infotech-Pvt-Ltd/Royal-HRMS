import { describe, expect, it } from "vitest";
import { fillLightState, flowParams } from "./flowParams";

describe("flowParams(true) - flow V2 ON", () => {
  it("uses the V2 timing", () => {
    expect(flowParams(true)).toMatchObject({ stableFramesToStartLiveness: 5, livenessTimeoutMs: 9000, multiFrameIntervalMs: 250 });
  });

  it("turns every V2 feature on", () => {
    expect(flowParams(true)).toMatchObject({ readinessGate: true, luminanceSampling: true, cameraBoost: true, guideOval: true });
  });
});

describe("flowParams(false) - flow V2 OFF restores the original capture behaviour", () => {
  it("restores the original 10-frame start, 12-second liveness window and 350 ms frame spacing", () => {
    expect(flowParams(false)).toMatchObject({ stableFramesToStartLiveness: 10, livenessTimeoutMs: 12000, multiFrameIntervalMs: 350 });
  });

  it("turns every V2-only feature off: no readiness gate, no hints source, no camera boost, no oval", () => {
    expect(flowParams(false)).toMatchObject({ readinessGate: false, luminanceSampling: false, cameraBoost: false, guideOval: false });
  });

  it("every V2 feature flag is false, so none can stay active by accident", () => {
    const { readinessGate, luminanceSampling, cameraBoost, guideOval } = flowParams(false);
    expect([readinessGate, luminanceSampling, cameraBoost, guideOval].every(flag => flag === false)).toBe(true);
  });

  it("the capture timing is unchanged in size: OFF is slower/more patient than ON, never the reverse", () => {
    const on = flowParams(true), off = flowParams(false);
    expect(off.stableFramesToStartLiveness).toBeGreaterThan(on.stableFramesToStartLiveness);
    expect(off.livenessTimeoutMs).toBeGreaterThan(on.livenessTimeoutMs);
    expect(off.multiFrameIntervalMs).toBeGreaterThan(on.multiFrameIntervalMs);
  });
});

describe("fillLightState - the white screen-as-a-light experience", () => {
  it("V2 ON: white backdrop while the camera is live; the tip only once the preview has been dim", () => {
    expect(fillLightState(true, true, false)).toEqual({ screenLight: true, fillLight: false });  // well lit: white, no tip
    expect(fillLightState(true, true, true)).toEqual({ screenLight: true, fillLight: true });    // dark: white + tip
  });

  it("V2 ON: normal dark backdrop and no tip when the camera is not live (loading, failure, closed)", () => {
    expect(fillLightState(true, false, false)).toEqual({ screenLight: false, fillLight: false });
    expect(fillLightState(true, false, true)).toEqual({ screenLight: false, fillLight: false });
  });

  it("V2 OFF: never a white screen and never the tip, in any lighting", () => {
    for (const live of [true, false]) {
      for (const dim of [true, false]) {
        expect(fillLightState(false, live, dim)).toEqual({ screenLight: false, fillLight: false });
      }
    }
  });
});
