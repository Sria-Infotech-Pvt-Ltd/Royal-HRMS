import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// face-api.js is mocked: these tests are about the loader's sequencing, state,
// timeouts and self-test - not about the real networks. No images, no real
// embeddings are involved anywhere.
const mocks = vi.hoisted(() => ({
  tinyLoad: vi.fn(),
  landmarkLoad: vi.fn(),
  recognitionLoad: vi.fn(),
  tinyDetect: vi.fn(),
  detectLandmarks: vi.fn(),
  computeFaceDescriptor: vi.fn(),
}));

vi.mock("face-api.js", () => ({
  nets: {
    tinyFaceDetector: { loadFromUri: mocks.tinyLoad },
    faceLandmark68Net: { loadFromUri: mocks.landmarkLoad, detectLandmarks: mocks.detectLandmarks },
    faceRecognitionNet: { loadFromUri: mocks.recognitionLoad, computeFaceDescriptor: mocks.computeFaceDescriptor },
  },
  tinyFaceDetector: mocks.tinyDetect,
  TinyFaceDetectorOptions: class TinyFaceDetectorOptions {},
}));

import {
  __resetModelLoaderForTests, describeModelLoadFailure, getModelLoadInfo, getModelLoadProgress,
  getModelLoadState, isDetectionReady, isRecognitionReady, loadDetectionModels, loadFaceApiModels,
  loadRecognitionModel, ModelLoadError, modelLoadingMessage, MODEL_STALL_TIMEOUT_MS, retryModelLoad,
  subscribeModelLoadState,
} from "./loadModels";

const FLAG = "NEXT_PUBLIC_FACE_LOADER_V2";
const DETECTION_FILE_COUNT = 4;
const RECOGNITION_FILE_COUNT = 3;
const ALL_FILE_COUNT = DETECTION_FILE_COUNT + RECOGNITION_FILE_COUNT;

function okResponse(chunks = 1) {
  let i = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () => (i++ < chunks
          ? { done: false, value: new Uint8Array(16) }
          : { done: true, value: undefined }),
      }),
    },
  };
}

/** A response whose chunks arrive `gapMs` apart (needs fake timers). */
function slowResponse(chunks: number, gapMs: number) {
  let i = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: () => new Promise(resolve => {
          setTimeout(() => {
            resolve(i++ < chunks ? { done: false, value: new Uint8Array(16) } : { done: true, value: undefined });
          }, gapMs);
        }),
      }),
    },
  };
}

/** A fetch that never answers until its request is aborted - a stalled connection. */
function stalledFetch(_url: string, init?: { signal?: AbortSignal }) {
  return new Promise((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new DOMException("The operation was aborted.", "AbortError")));
  });
}

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

const fetchMock = vi.fn();
const fetchedNames = () => fetchMock.mock.calls.map(call => String(call[0]).split("/").pop());

beforeEach(() => {
  __resetModelLoaderForTests();
  process.env[FLAG] = "1";
  fetchMock.mockReset();
  fetchMock.mockImplementation(async () => okResponse());
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("document", { createElement: () => ({ width: 0, height: 0, getContext: () => null }) });
  for (const m of Object.values(mocks)) m.mockReset();
  mocks.tinyLoad.mockResolvedValue(undefined);
  mocks.landmarkLoad.mockResolvedValue(undefined);
  mocks.recognitionLoad.mockResolvedValue(undefined);
  mocks.tinyDetect.mockResolvedValue(undefined);
  mocks.detectLandmarks.mockResolvedValue(undefined);
  mocks.computeFaceDescriptor.mockResolvedValue(new Float32Array(128).fill(0.01)); // a valid descriptor
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  delete process.env[FLAG];
});

describe("loading to ready", () => {
  it("goes idle -> loading -> ready, and reports both models ready", async () => {
    expect(getModelLoadState()).toBe("idle");
    const seen: string[] = [];
    const unsubscribe = subscribeModelLoadState(() => seen.push(getModelLoadState()));

    await loadFaceApiModels();
    unsubscribe();

    expect(seen[0]).toBe("loading");
    expect(seen[seen.length - 1]).toBe("ready");
    expect(getModelLoadState()).toBe("ready");
    expect(isDetectionReady()).toBe(true);
    expect(isRecognitionReady()).toBe(true);
    expect(getModelLoadProgress()).toBe(1);
    expect(getModelLoadInfo().failureReason).toBeNull();
  });

  it("is only 'ready' once BOTH stages are loaded", async () => {
    await loadDetectionModels();
    expect(isDetectionReady()).toBe(true);
    expect(isRecognitionReady()).toBe(false);
    expect(getModelLoadState()).toBe("loading");
    await loadRecognitionModel();
    expect(getModelLoadState()).toBe("ready");
  });
});

describe("shared load operation", () => {
  it("concurrent calls share one load: every file is fetched and every net loaded once", async () => {
    await Promise.all([
      loadDetectionModels(), loadDetectionModels(), loadRecognitionModel(),
      loadFaceApiModels(), loadRecognitionModel(), loadDetectionModels(),
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(ALL_FILE_COUNT);
    expect(new Set(fetchedNames()).size).toBe(ALL_FILE_COUNT);
    expect(mocks.tinyLoad).toHaveBeenCalledTimes(1);
    expect(mocks.landmarkLoad).toHaveBeenCalledTimes(1);
    expect(mocks.recognitionLoad).toHaveBeenCalledTimes(1);
  });

  it("calling again after success does no further work", async () => {
    await loadFaceApiModels();
    fetchMock.mockClear();
    await loadFaceApiModels();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(mocks.recognitionLoad).toHaveBeenCalledTimes(1);
  });
});

describe("failure and retry", () => {
  it("a network failure ends in 'failed' with a reason (each file tried twice)", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(loadFaceApiModels()).rejects.toBeInstanceOf(ModelLoadError);
    expect(getModelLoadState()).toBe("failed");
    expect(getModelLoadInfo().failureReason).toBe("network");
    expect(isDetectionReady()).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(DETECTION_FILE_COUNT * 2); // one automatic retry per file
  });

  it("an HTTP 404 fails straight away without a retry", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 404, body: null });
    await expect(loadDetectionModels()).rejects.toMatchObject({ reason: "http", status: 404 });
    expect(fetchMock).toHaveBeenCalledTimes(DETECTION_FILE_COUNT);
    expect(getModelLoadState()).toBe("failed");
  });

  it("an HTTP 503 is retried once, and succeeds if the retry does", async () => {
    let calls = 0;
    fetchMock.mockImplementation(async () => (calls++ === 0 ? { ok: false, status: 503, body: null } : okResponse()));
    await loadDetectionModels();
    expect(isDetectionReady()).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(DETECTION_FILE_COUNT + 1);
  });

  it("retry succeeds without a page reload", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(loadFaceApiModels()).rejects.toBeInstanceOf(ModelLoadError);
    expect(getModelLoadState()).toBe("failed");

    fetchMock.mockReset();
    fetchMock.mockImplementation(async () => okResponse()); // the connection is back
    await retryModelLoad();

    expect(getModelLoadState()).toBe("ready");
    expect(getModelLoadInfo().failureReason).toBeNull();
    expect(isDetectionReady()).toBe(true);
    expect(isRecognitionReady()).toBe(true);
  });

  it("a failed recognition stage can be retried on its own", async () => {
    mocks.recognitionLoad.mockRejectedValueOnce(new Error("bad weights"));
    await loadDetectionModels();
    await expect(loadRecognitionModel()).rejects.toThrow("bad weights");
    expect(getModelLoadState()).toBe("failed");
    expect(isDetectionReady()).toBe(true); // the small stage is unaffected

    await loadRecognitionModel(); // second attempt succeeds
    expect(isRecognitionReady()).toBe(true);
    expect(getModelLoadState()).toBe("ready");
  });
});

describe("stall timeout", () => {
  it("aborts a stalled request after 30 s, retries once, then fails with a timeout", async () => {
    vi.useFakeTimers();
    expect(MODEL_STALL_TIMEOUT_MS).toBe(30_000);
    fetchMock.mockImplementation(stalledFetch);

    const outcome = loadDetectionModels().then(() => null, (err: unknown) => err);

    await vi.advanceTimersByTimeAsync(29_000);
    expect(fetchMock).toHaveBeenCalledTimes(DETECTION_FILE_COUNT); // still waiting on the first attempts
    expect(getModelLoadState()).toBe("loading");

    await vi.advanceTimersByTimeAsync(2_000); // 31 s: first attempts aborted, the automatic retry begins
    expect(fetchMock).toHaveBeenCalledTimes(DETECTION_FILE_COUNT * 2);
    expect(getModelLoadState()).toBe("loading");

    await vi.advanceTimersByTimeAsync(31_000); // the retries stall too
    const err = await outcome;

    expect(err).toBeInstanceOf(ModelLoadError);
    expect((err as ModelLoadError).reason).toBe("timeout");
    expect(getModelLoadState()).toBe("failed");
    expect(getModelLoadInfo().failureReason).toBe("timeout");
    expect(describeModelLoadFailure(err).code).toBe("models_timeout");
  });

  it("does not kill a slow download that keeps making progress", async () => {
    vi.useFakeTimers();
    // A chunk every 20 s for ~80 s in total: far longer than 30 s, but never 30 s without progress.
    fetchMock.mockImplementation(async () => slowResponse(3, 20_000));

    const done = loadDetectionModels();
    await vi.advanceTimersByTimeAsync(90_000);
    await done;

    expect(isDetectionReady()).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(DETECTION_FILE_COUNT); // no timeout, so no retry
  });
});

describe("recognition self-test", () => {
  it("rejects wrong-length output and does not mark the model ready", async () => {
    mocks.computeFaceDescriptor.mockResolvedValue(new Float32Array(64).fill(0.01));
    await expect(loadRecognitionModel()).rejects.toMatchObject({ reason: "self_test" });
    expect(isRecognitionReady()).toBe(false);
    expect(getModelLoadState()).toBe("failed");
    expect(getModelLoadInfo().failureReason).toBe("self_test");
  });

  it("rejects non-finite values (NaN)", async () => {
    const bad = new Float32Array(128).fill(0.01);
    bad[5] = Number.NaN;
    mocks.computeFaceDescriptor.mockResolvedValue(bad);
    await expect(loadRecognitionModel()).rejects.toMatchObject({ reason: "self_test" });
    expect(isRecognitionReady()).toBe(false);
  });

  it("rejects non-finite values (Infinity)", async () => {
    const bad = new Float32Array(128).fill(0.01);
    bad[100] = Number.POSITIVE_INFINITY;
    mocks.computeFaceDescriptor.mockResolvedValue(bad);
    await expect(loadRecognitionModel()).rejects.toMatchObject({ reason: "self_test" });
    expect(isRecognitionReady()).toBe(false);
  });

  it("rejects when the inference itself throws", async () => {
    mocks.computeFaceDescriptor.mockRejectedValue(new Error("webgl context lost"));
    await expect(loadRecognitionModel()).rejects.toMatchObject({ reason: "self_test" });
    expect(isRecognitionReady()).toBe(false);
  });

  it("accepts a valid 128-value output and reports a distinct telemetry code when it fails", async () => {
    await loadRecognitionModel();
    expect(isRecognitionReady()).toBe(true);
    expect(describeModelLoadFailure(new ModelLoadError("self_test", "x")).code).toBe("models_self_test_failed");
    expect(describeModelLoadFailure(new ModelLoadError("network", "x")).code).toBe("models_failed");
    expect(describeModelLoadFailure(new Error("anything")).code).toBe("models_failed");
  });

  it("failing the self-test records no descriptor values in the error", async () => {
    const bad = new Float32Array(128).fill(0.123456);
    bad[1] = Number.NaN;
    mocks.computeFaceDescriptor.mockResolvedValue(bad);
    const err = await loadRecognitionModel().then(() => null, (e: unknown) => e as Error);
    expect(err?.message).not.toContain("0.123456");
  });
});

describe("capture gating", () => {
  it("the detector gate stays closed until its models have actually loaded", async () => {
    const gate = deferred();
    mocks.tinyLoad.mockReturnValue(gate.promise);

    let resolved = false;
    const gateForCapture = loadDetectionModels().then(() => { resolved = true; });
    await vi.waitFor(() => expect(mocks.tinyLoad).toHaveBeenCalled());
    await new Promise(r => setTimeout(r, 0));

    expect(resolved).toBe(false);
    expect(isDetectionReady()).toBe(false);
    expect(getModelLoadState()).toBe("loading");

    gate.resolve();
    await gateForCapture;
    expect(resolved).toBe(true);
    expect(isDetectionReady()).toBe(true);
  });

  it("the final-capture gate stays closed until the recognition model has loaded and passed its self-test", async () => {
    const gate = deferred();
    mocks.recognitionLoad.mockReturnValue(gate.promise);
    await loadDetectionModels();

    let resolved = false;
    const gateForFinalCapture = loadRecognitionModel().then(() => { resolved = true; });
    await vi.waitFor(() => expect(mocks.recognitionLoad).toHaveBeenCalled());
    await new Promise(r => setTimeout(r, 0));

    expect(resolved).toBe(false);
    expect(isRecognitionReady()).toBe(false);
    expect(mocks.computeFaceDescriptor).not.toHaveBeenCalled(); // the self-test cannot run before the net has loaded

    gate.resolve();
    await gateForFinalCapture;
    expect(isRecognitionReady()).toBe(true);
  });
});

describe("overlapping the recognition download", () => {
  it("V2: the recognition files are requested while the detector is still loading, but the recognition net loads only afterwards", async () => {
    const detectorGate = deferred();
    mocks.tinyLoad.mockReturnValue(detectorGate.promise);

    const all = loadFaceApiModels();
    await vi.waitFor(() => expect(fetchedNames()).toContain("face_recognition_model-shard1"));

    expect(isDetectionReady()).toBe(false);
    expect(mocks.recognitionLoad).not.toHaveBeenCalled(); // never two nets initialising at once

    detectorGate.resolve();
    await all;
    expect(mocks.recognitionLoad).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(ALL_FILE_COUNT); // overlapping did not duplicate any download
  });

  it("flag off: the old ordering is unchanged - recognition files wait for the detector stage to finish", async () => {
    delete process.env[FLAG];
    const detectorGate = deferred();
    mocks.tinyLoad.mockReturnValue(detectorGate.promise);

    const all = loadFaceApiModels();
    await vi.waitFor(() => expect(mocks.tinyLoad).toHaveBeenCalled());
    await new Promise(r => setTimeout(r, 0));
    expect(fetchedNames()).not.toContain("face_recognition_model-shard1");

    detectorGate.resolve();
    await all;
    expect(fetchedNames()).toContain("face_recognition_model-shard1");
  });

  it("flag off: no stall timeout and no self-test (old behaviour), so an invalid output does not fail the load", async () => {
    delete process.env[FLAG];
    mocks.computeFaceDescriptor.mockResolvedValue(new Float32Array(64));
    await loadFaceApiModels();
    expect(isRecognitionReady()).toBe(true);
  });
});

describe("cache detection and messages", () => {
  function stubTiming(entry: { decodedBodySize: number; transferSize: number } | null) {
    vi.stubGlobal("window", { location: { href: "http://localhost/dashboard" } });
    vi.spyOn(performance, "getEntriesByName").mockImplementation(
      () => (entry ? [entry as unknown as PerformanceEntry] : []),
    );
  }

  it("reports 'hit' when the shards transferred (almost) nothing", async () => {
    stubTiming({ decodedBodySize: 4_000_000, transferSize: 0 });
    await loadFaceApiModels();
    expect(getModelLoadInfo().cache).toBe("hit");
  });

  it("reports 'miss' when the shards were really downloaded", async () => {
    stubTiming({ decodedBodySize: 4_000_000, transferSize: 4_000_300 });
    await loadFaceApiModels();
    expect(getModelLoadInfo().cache).toBe("miss");
  });

  it("reports 'unknown' when timing data is unavailable", async () => {
    stubTiming(null);
    await loadFaceApiModels();
    expect(getModelLoadInfo().cache).toBe("unknown");
  });

  it("says 'Downloading' only while downloading, 'Preparing' otherwise", () => {
    expect(modelLoadingMessage("downloading")).toBe("Downloading face verification models…");
    expect(modelLoadingMessage("preparing")).toBe("Preparing face verification…");
  });

  it("flips to the downloading phase only when a request is genuinely pending, and back afterwards", async () => {
    vi.useFakeTimers();
    const gate = deferred<ReturnType<typeof okResponse>>();
    fetchMock.mockImplementation(() => gate.promise);

    const done = loadDetectionModels();
    expect(getModelLoadInfo().phase).toBe("preparing"); // nothing slow yet: could be the cache
    await vi.advanceTimersByTimeAsync(300);
    expect(getModelLoadInfo().phase).toBe("downloading");

    gate.resolve(okResponse());
    await vi.advanceTimersByTimeAsync(0);
    await done;
    expect(getModelLoadInfo().phase).toBe("preparing");
  });

  it("flag off: keeps the original loading text", () => {
    delete process.env[FLAG];
    expect(modelLoadingMessage("preparing")).toBe("Downloading face models (first time only)…");
  });
});
