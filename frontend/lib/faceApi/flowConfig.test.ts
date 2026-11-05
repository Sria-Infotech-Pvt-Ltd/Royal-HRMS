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
