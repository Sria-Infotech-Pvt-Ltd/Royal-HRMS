import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  state: { value: "idle" as "idle" | "loading" | "ready" | "failed" },
  load: vi.fn(() => Promise.resolve()),
}));

vi.mock("./loadModels", () => ({
  getModelLoadState: () => mocks.state.value,
  loadFaceApiModels: mocks.load,
}));

import { __resetPreloadForTests, scheduleFaceModelPreload } from "./preload";

let idleCallbacks: Array<{ id: number; cb: () => void }> = [];
let nextId = 1;
const cancelIdle = vi.fn((id: number) => { idleCallbacks = idleCallbacks.filter(c => c.id !== id); });

beforeEach(() => {
  __resetPreloadForTests();
  mocks.state.value = "idle";
  mocks.load.mockClear();
  cancelIdle.mockClear();
  idleCallbacks = [];
  nextId = 1;
  vi.stubGlobal("window", {
    requestIdleCallback: (cb: () => void) => { const id = nextId++; idleCallbacks.push({ id, cb }); return id; },
    cancelIdleCallback: cancelIdle,
    setTimeout, clearTimeout,
  });
});

afterEach(() => vi.unstubAllGlobals());

const runIdle = () => idleCallbacks.splice(0).forEach(c => c.cb());

describe("scheduleFaceModelPreload - the single preload entry point", () => {
  it("two callers (dashboard preloader + clock widget) schedule ONE idle task and ONE load", () => {
    scheduleFaceModelPreload();
    scheduleFaceModelPreload();
    expect(idleCallbacks).toHaveLength(1);
    runIdle();
    expect(mocks.load).toHaveBeenCalledTimes(1);
  });

  it("does nothing while the models are loading or already ready", () => {
    mocks.state.value = "loading";
    scheduleFaceModelPreload();
    mocks.state.value = "ready";
    scheduleFaceModelPreload();
    expect(idleCallbacks).toHaveLength(0);
    expect(mocks.load).not.toHaveBeenCalled();
  });

  it("schedules again after a failure (the next mount gets a fresh attempt)", () => {
    mocks.state.value = "failed";
    scheduleFaceModelPreload();
    runIdle();
    expect(mocks.load).toHaveBeenCalledTimes(1);
  });

  it("cancels the shared task only when every caller has cancelled", () => {
    const cancelA = scheduleFaceModelPreload();
    const cancelB = scheduleFaceModelPreload();
    cancelA();
    expect(cancelIdle).not.toHaveBeenCalled();
    expect(idleCallbacks).toHaveLength(1);
    cancelB();
    expect(cancelIdle).toHaveBeenCalledTimes(1);
    expect(idleCallbacks).toHaveLength(0);
    runIdle();
    expect(mocks.load).not.toHaveBeenCalled();
  });

  it("a cancel function is safe to call twice", () => {
    const cancelA = scheduleFaceModelPreload();
    const cancelB = scheduleFaceModelPreload();
    cancelA();
    cancelA(); // must not steal the other caller's reference
    expect(idleCallbacks).toHaveLength(1);
    cancelB();
    expect(idleCallbacks).toHaveLength(0);
  });

  it("a failed preload is swallowed (the clock-in flow surfaces and retries it)", async () => {
    mocks.load.mockRejectedValueOnce(new Error("offline"));
    scheduleFaceModelPreload();
    expect(() => runIdle()).not.toThrow();
    await Promise.resolve();
  });

  it("is a no-op outside the browser", () => {
    vi.unstubAllGlobals(); // no window in Node
    const cancel = scheduleFaceModelPreload();
    expect(typeof cancel).toBe("function");
    expect(mocks.load).not.toHaveBeenCalled();
  });
});
