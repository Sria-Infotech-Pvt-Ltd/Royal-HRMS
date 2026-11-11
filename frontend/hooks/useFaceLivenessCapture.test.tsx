// @vitest-environment jsdom
//
// Integration test for the descriptor-validation WIRING in useFaceLivenessCapture
// (and, through it, useFaceRegistrationCapture): an invalid descriptor - wrong
// length or containing a non-finite value - must never reach onCaptured (which
// is what registration and clock-in verification both consume) and so can never
// be submitted.
//
// What is REAL here: the hooks themselves, the loader (lib/faceApi/loadModels),
// the quality gate, the consistency check, the multi-frame averaging, the
// telemetry class. What is mocked: only the browser/ML edges - face-api.js
// output (detections + the per-frame descriptors the test controls), the camera
// stream, the canvas pixel helpers, the liveness tracker (always "passed", so
// the flow reaches capture), and the HTTP client (so nothing leaves the test).
// No image, no real biometric embedding, and no network request is involved:
// the descriptors are synthetic numbers.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { flushSync } from "react-dom";
import { createElement } from "react";

const SENTINEL = 0.123456; // a distinctive value that must never appear in telemetry

const hoisted = vi.hoisted(() => ({
  /** Descriptor returned for each successive captured frame (the test sets this). */
  frameDescriptor: { make: (): Float32Array => new Float32Array(128) },
  post: vi.fn(),
  track: { stop: vi.fn() },
}));

vi.mock("face-api.js", () => {
  const landmarks = {
    getLeftEye: () => [{ x: 90, y: 100 }, { x: 110, y: 100 }],
    getRightEye: () => [{ x: 190, y: 100 }, { x: 210, y: 100 }],
    getNose: () => [{ x: 150, y: 110 }, { x: 150, y: 120 }, { x: 150, y: 130 }, { x: 150, y: 140 }, { x: 150, y: 150 }],
  };
  const detection = { box: { x: 50, y: 50, width: 200, height: 200 }, score: 0.95 };
  return {
    nets: {
      tinyFaceDetector: { loadFromUri: async () => undefined },
      faceLandmark68Net: { loadFromUri: async () => undefined, detectLandmarks: async () => undefined },
      faceRecognitionNet: {
        loadFromUri: async () => undefined,
        computeFaceDescriptor: async () => new Float32Array(128).fill(0.01), // the loader's own self-test: valid
      },
    },
    tinyFaceDetector: async () => undefined,
    TinyFaceDetectorOptions: class TinyFaceDetectorOptions {},
    tf: { getBackend: () => "webgl" },
    detectSingleFace: () => ({ withFaceLandmarks: async () => ({ detection, landmarks }) }),
    detectAllFaces: () => ({
      withFaceLandmarks: () => ({
        withFaceDescriptors: async () => [{ detection, landmarks, descriptor: hoisted.frameDescriptor.make() }],
      }),
    }),
  };
});

vi.mock("@/lib/clientApi", () => ({ default: { post: hoisted.post } }));

vi.mock("@/lib/faceApi/liveness", () => ({
  LivenessTracker: class {
    setMode() {}
    reset() {}
    addSample() {}
    getResult() { return { passed: true, score: 0.9 }; }
    getProgress() { return { blink: true, turn: true }; }
  },
}));
vi.mock("@/lib/faceApi/guide", () => ({ faceInsideGuide: () => true }));
vi.mock("@/lib/faceApi/readiness", () => ({
  assessLiveReadiness: () => ({ ready: true, code: null, hint: null, lowLight: false }),
}));
vi.mock("@/lib/faceApi/overlay", () => ({
  syncCanvasSize: () => undefined,
  drawDetectionBox: () => undefined,
  clearOverlay: () => undefined,
  OVERLAY_COLOR: { detecting: "", checking: "", passed: "" },
}));
vi.mock("@/lib/faceApi/clahe", () => ({ applyClahe: () => undefined }));
vi.mock("@/lib/faceApi/frameCapture", () => ({
  grabVideoFrame: () => ({ width: 640, height: 480, data: new Uint8ClampedArray(4) }),
  putImageData: () => undefined,
  meanLuminanceOfBox: () => 120,
  assessEyeOcclusion: () => ({ suspected: false }),
  sampleFaceAndFrameLuminance: () => ({ face: 120, frame: 120 }),
}));

import { useFaceLivenessCapture, type LivenessCapturePhase } from "./useFaceLivenessCapture";
import { useFaceRegistrationCapture } from "./useFaceRegistrationCapture";
import { __resetModelLoaderForTests } from "@/lib/faceApi/loadModels";
import { API } from "@/lib/api/endpoints";

const FLAG = "NEXT_PUBLIC_FACE_LOADER_V2";

// ─── Environment stubs (jsdom has no camera, no video playback, no canvas) ──

function okResponse() {
  let done = false;
  return {
    ok: true, status: 200,
    body: { getReader: () => ({ read: async () => (done ? { done: true, value: undefined } : (done = true, { done: false, value: new Uint8Array(8) })) }) },
  };
}

beforeEach(() => {
  __resetModelLoaderForTests();
  process.env[FLAG] = "1";
  hoisted.post.mockReset();
  hoisted.post.mockResolvedValue({ data: { data: { id: "req-1", status: "pending" } } });
  hoisted.track.stop.mockReset();

  vi.stubGlobal("fetch", vi.fn(async () => okResponse()));
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => setTimeout(() => cb(performance.now()), 4) as unknown as number);
  vi.stubGlobal("cancelAnimationFrame", (id: number) => clearTimeout(id));

  const track = { stop: hoisted.track.stop, getCapabilities: () => ({}), getSettings: () => ({}), applyConstraints: async () => undefined };
  const stream = { getTracks: () => [track], getVideoTracks: () => [track] };
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn(async () => stream) }, configurable: true,
  });
  HTMLCanvasElement.prototype.getContext = (() => null) as never;
  HTMLMediaElement.prototype.play = (async () => undefined) as never;
  Object.defineProperty(HTMLMediaElement.prototype, "readyState", { get: () => 4, configurable: true });
  Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", { get: () => 640, configurable: true });
  Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", { get: () => 480, configurable: true });
});

let root: Root | null = null;
let container: HTMLElement | null = null;

afterEach(() => {
  root?.unmount();
  container?.remove();
  root = null;
  container = null;
  vi.unstubAllGlobals();
  delete process.env[FLAG];
});

/** A frame descriptor that is `length` long, filled with the sentinel (optionally with one NaN). */
function descriptorOf(length: number, nanAt?: number) {
  return () => {
    const d = new Float32Array(length).fill(SENTINEL);
    if (nanAt !== undefined) d[nanAt] = Number.NaN;
    return d;
  };
}

// ─── Harnesses: the REAL hooks, rendered into jsdom ─────────────────────────

interface CaptureApi {
  phase: LivenessCapturePhase;
  errorMessage: string | null;
  start: () => void;
}

function mount(node: ReturnType<typeof createElement>) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  flushSync(() => root!.render(node));
}

function renderVerificationHook(onCaptured: (...args: unknown[]) => void, framesToCapture: number) {
  const apiRef: { current: CaptureApi | null } = { current: null };
  function Harness() {
    const api = useFaceLivenessCapture({
      onCaptured: onCaptured as never, framesToCapture, normalizeLighting: true, purpose: "verify", livenessMode: "turn_only",
    });
    apiRef.current = api;
    return createElement("div", null, createElement("video", { ref: api.videoRef }), createElement("canvas", { ref: api.canvasRef }));
  }
  mount(createElement(Harness));
  return apiRef;
}

function renderRegistrationHook() {
  const apiRef: { current: (CaptureApi & { start: (consent: boolean) => void }) | null } = { current: null };
  function Harness() {
    const api = useFaceRegistrationCapture();
    apiRef.current = api as never;
    return createElement("div", null, createElement("video", { ref: api.videoRef }), createElement("canvas", { ref: api.canvasRef }));
  }
  mount(createElement(Harness));
  return apiRef;
}

const telemetryPosts = () =>
  hoisted.post.mock.calls.filter(call => call[0] === API.attendance.faceCaptureTelemetry);
const registrationPosts = () =>
  hoisted.post.mock.calls.filter(call => call[0] === API.attendance.faceRegistration.submit);

async function expectBlockedWithError(apiRef: { current: CaptureApi | null }, onCaptured: ReturnType<typeof vi.fn>) {
  await vi.waitFor(() => expect(apiRef.current?.phase).toBe("error"), { timeout: 15_000 });
  expect(onCaptured).not.toHaveBeenCalled();
  expect(apiRef.current?.errorMessage).toMatch(/valid result/i);
  expect(hoisted.track.stop).toHaveBeenCalled(); // the camera is released

  // The failure is observable, with a distinct code, and carries no biometric values.
  await vi.waitFor(() => expect(telemetryPosts()).toHaveLength(1));
  const payload = telemetryPosts()[0][1] as { outcome: string; details: { failure_reasons: Record<string, number> } };
  expect(payload.outcome).toBe("error");
  expect(payload.details.failure_reasons.descriptor_invalid).toBe(1);
  expect(JSON.stringify(payload)).not.toContain(String(SENTINEL));
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe("useFaceLivenessCapture: an invalid descriptor cannot proceed (loader V2 on)", () => {
  it("wrong length (127 values, all frames mutually consistent): onCaptured is never called", async () => {
    hoisted.frameDescriptor.make = descriptorOf(127);
    const onCaptured = vi.fn();
    const apiRef = renderVerificationHook(onCaptured, 3); // the clock-in frame count
    apiRef.current!.start();
    await expectBlockedWithError(apiRef, onCaptured);
  }, 30_000);

  it("a non-finite value (NaN in a single-frame capture): onCaptured is never called", async () => {
    hoisted.frameDescriptor.make = descriptorOf(128, 7);
    const onCaptured = vi.fn();
    const apiRef = renderVerificationHook(onCaptured, 1);
    apiRef.current!.start();
    await expectBlockedWithError(apiRef, onCaptured);
  }, 30_000);

  it("a non-finite value across several frames is stopped by the consistency check and never submitted", async () => {
    hoisted.frameDescriptor.make = descriptorOf(128, 7);
    const onCaptured = vi.fn();
    const apiRef = renderVerificationHook(onCaptured, 3);
    apiRef.current!.start();
    // NaN distances fail the cross-frame consistency check; after its automatic
    // resumes the capture ends in quality_failed - never in a submitted descriptor.
    await vi.waitFor(() => expect(apiRef.current?.phase).toBe("quality_failed"), { timeout: 25_000 });
    expect(onCaptured).not.toHaveBeenCalled();
  }, 40_000);

  it("control: a valid 128-value descriptor is delivered to onCaptured", async () => {
    hoisted.frameDescriptor.make = () => new Float32Array(128).fill(0.02);
    const onCaptured = vi.fn();
    const apiRef = renderVerificationHook(onCaptured, 3);
    apiRef.current!.start();

    await vi.waitFor(() => expect(onCaptured).toHaveBeenCalledTimes(1), { timeout: 15_000 });
    const [descriptor, , , meta] = onCaptured.mock.calls[0] as [number[], number, string, { frameCount: number }];
    expect(descriptor).toHaveLength(128);
    expect(descriptor.every(Number.isFinite)).toBe(true);
    expect(meta.frameCount).toBe(3);
    await vi.waitFor(() => expect(apiRef.current?.phase).toBe("captured"));
  }, 30_000);
});

describe("registration: an invalid descriptor is never submitted", () => {
  it("wrong length: no registration request is sent", async () => {
    hoisted.frameDescriptor.make = descriptorOf(127);
    const apiRef = renderRegistrationHook();
    apiRef.current!.start(true);

    await vi.waitFor(() => expect(apiRef.current?.phase).toBe("error"), { timeout: 20_000 });
    expect(registrationPosts()).toHaveLength(0);
    await vi.waitFor(() => expect(telemetryPosts()).toHaveLength(1));
    expect(JSON.stringify(hoisted.post.mock.calls)).not.toContain(String(SENTINEL));
  }, 40_000);

  it("control: a valid descriptor is submitted exactly once, as 128 finite values", async () => {
    hoisted.frameDescriptor.make = () => new Float32Array(128).fill(0.02);
    const apiRef = renderRegistrationHook();
    apiRef.current!.start(true);

    await vi.waitFor(() => expect(registrationPosts()).toHaveLength(1), { timeout: 20_000 });
    const body = registrationPosts()[0][1] as { face_embedding: number[]; liveness_passed: boolean };
    expect(body.face_embedding).toHaveLength(128);
    expect(body.face_embedding.every(Number.isFinite)).toBe(true);
    expect(body.liveness_passed).toBe(true);
  }, 40_000);
});

describe("rollback: loader V2 off keeps the previous behaviour", () => {
  it("the final-descriptor check is part of V2 only - with the flag off the capture is delivered as before", async () => {
    delete process.env[FLAG];
    hoisted.frameDescriptor.make = descriptorOf(127);
    const onCaptured = vi.fn();
    const apiRef = renderVerificationHook(onCaptured, 3);
    apiRef.current!.start();

    await vi.waitFor(() => expect(onCaptured).toHaveBeenCalledTimes(1), { timeout: 15_000 });
    expect((onCaptured.mock.calls[0][0] as number[]).length).toBe(127); // no V2 validation (the server would reject it)
  }, 30_000);
});
