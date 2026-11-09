import { afterEach, describe, expect, it, vi } from "vitest";

// FACE_FLOW_V2 is read once, when the module loads (it is a build-time NEXT_PUBLIC_ value), so each case sets the
// variable first and then imports a fresh copy of the module.
async function loadFlag(value: string | undefined): Promise<boolean> {
  vi.resetModules();
  if (value === undefined) vi.stubEnv("NEXT_PUBLIC_FACE_FLOW_V2", undefined as unknown as string);
  else vi.stubEnv("NEXT_PUBLIC_FACE_FLOW_V2", value);
  const mod = await import("./flowConfig");
  return mod.FACE_FLOW_V2;
}

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

describe("FACE_FLOW_V2 kill switch", () => {
  it("is ON by default (variable not set)", async () => {
    expect(await loadFlag(undefined)).toBe(true);
  });

  it("is ON for any value other than \"0\"", async () => {
    expect(await loadFlag("1")).toBe(true);
    expect(await loadFlag("true")).toBe(true);
    expect(await loadFlag("")).toBe(true);
  });

  it("is OFF only when set to \"0\"", async () => {
    expect(await loadFlag("0")).toBe(false);
  });
});

// The flag is what picks the whole flow: every consumer calls flowParams(FACE_FLOW_V2) / fillLightState(FACE_FLOW_V2, ...).
// These prove the resolved flag really selects the original (OFF) or V2 (ON) parameter set end to end.
describe("FACE_FLOW_V2 selects the flow", () => {
  async function paramsFor(value: string | undefined) {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_FACE_FLOW_V2", value as unknown as string);
    const { FACE_FLOW_V2 } = await import("./flowConfig");
    const { flowParams, fillLightState } = await import("./flowParams");
    return { flag: FACE_FLOW_V2, params: flowParams(FACE_FLOW_V2), light: fillLightState(FACE_FLOW_V2, true, true) };
  }

  it("=0 selects the original flow: no guide oval, readiness gate, boost or fill light; original timings", async () => {
    const { flag, params, light } = await paramsFor("0");
    expect(flag).toBe(false);
    expect(params).toEqual({
      stableFramesToStartLiveness: 10, livenessTimeoutMs: 12000, multiFrameIntervalMs: 350,
      readinessGate: false, luminanceSampling: false, cameraBoost: false, guideOval: false,
    });
    expect(light).toEqual({ screenLight: false, fillLight: false });
  });

  it("=1 selects V2: guide oval, readiness gate, boost, fill light, faster timings", async () => {
    const { flag, params, light } = await paramsFor("1");
    expect(flag).toBe(true);
    expect(params).toEqual({
      stableFramesToStartLiveness: 5, livenessTimeoutMs: 9000, multiFrameIntervalMs: 250,
      readinessGate: true, luminanceSampling: true, cameraBoost: true, guideOval: true,
    });
    expect(light).toEqual({ screenLight: true, fillLight: true });
  });

  it("missing or unexpected values (\"false\", \" 0\", \"00\", \"off\") stay ON - only the exact string \"0\" disables V2", async () => {
    for (const v of [undefined, "false", " 0", "00", "off", "2"]) {
      expect((await paramsFor(v)).flag, String(v)).toBe(true);
    }
  });
});
