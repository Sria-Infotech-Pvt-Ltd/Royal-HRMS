// Loads the three face-api.js models the face flows need, from the
// self-hosted weights in public/models/ (see public/models/README.md for
// provenance - pinned to a specific face-api.js commit, not a CDN).
//
//   tinyFaceDetector   - locates the face in each video frame (fast enough
//                        to run every frame for the live preview + liveness
//                        tracking).
//   faceLandmark68Net  - the 68-point landmark map used for the liveness
//                        check (eye/nose position tracking across frames).
//   faceRecognitionNet - generates the 128-d descriptor that becomes
//                        face_embedding. Its identity is exactly what the
//                        backend's FACE_RECOGNITION_MODEL_VERSION constant
//                        ('face-api.js-faceRecognitionNet-v1') pins the
//                        stored vector space to - never swap this model
//                        without also changing that backend constant.
//
// The models are the SAME common files for every user (one set per browser,
// cached on the device) - nothing here is per-employee; an employee's own data
// is only the stored descriptor on the server.
//
// Loaded in two stages because of size: the detector + landmarks (~0.55 MB)
// are all the live preview and liveness challenge need, so the camera can start
// as soon as they are in; the recognition net (~6.5 MB, nearly all of the
// download) is only needed for the final descriptor, so it keeps downloading
// while the person is busy blinking and turning their head.
//
// Reliability layer (NEXT_PUBLIC_FACE_LOADER_V2=1, see flowConfig.ts - OFF by
// default, and with it off the loading sequence below behaves exactly as it
// did before):
//   * an observable state, idle -> loading -> ready | failed, plus which phase
//     (downloading vs preparing) the camera-gating stage is in;
//   * the recognition download starts as soon as the small detector files are
//     in, in parallel with the detector's load + warm-up (only the recognition
//     net's own load/warm-up still waits for the detector, so the two never run
//     inference concurrently);
//   * a 30 s no-progress stall timeout per file with one automatic retry;
//   * a recognition self-test (exactly 128 finite values) before "ready".
// Nothing here touches thresholds, liveness, the quality gate or matching.
import * as faceapi from "face-api.js";
import { isFaceLoaderV2 } from "./flowConfig";
import { isValidDescriptor } from "./descriptor";

const MODEL_URL = "/models";

/** A model file that makes no progress for this long is aborted (then retried once). */
export const MODEL_STALL_TIMEOUT_MS = 30_000;
/** A fetch still pending after this long is real network work, so the UI may say "Downloading". */
const DOWNLOADING_AFTER_MS = 250;

// Approximate byte sizes of the files in public/models/ - only used to turn
// "bytes received so far" into a 0-1 progress fraction for the loading UI, so
// being a little off is harmless. Keep the filenames in sync with that folder.
const DETECTION_FILES: Record<string, number> = {
  "tiny_face_detector_model-weights_manifest.json": 3_000,
  "tiny_face_detector_model-shard1": 193_321,
  "face_landmark_68_model-weights_manifest.json": 8_000,
  "face_landmark_68_model-shard1": 356_840,
};
const RECOGNITION_FILES: Record<string, number> = {
  "face_recognition_model-weights_manifest.json": 18_500,
  "face_recognition_model-shard1": 4_194_304,
  "face_recognition_model-shard2": 2_249_728,
};

// ─── Observable state ─────────────────────────────────────────────────────

export type ModelLoadState = "idle" | "loading" | "ready" | "failed";
/** What the camera-gating (detector) stage is doing: pulling bytes, or initialising/warming up. */
export type ModelLoadPhase = "downloading" | "preparing";
export type ModelFailureReason = "timeout" | "network" | "http" | "self_test" | "init";
/** Whether the model files appear to have come from the browser cache ("unknown" when it can't be told reliably). */
export type ModelCacheStatus = "hit" | "miss" | "partial" | "unknown";

export interface ModelLoadInfo {
  state: ModelLoadState;
  phase: ModelLoadPhase;
  failureReason: ModelFailureReason | null;
  cache: ModelCacheStatus;
}

/** Thrown by the loader with a machine-readable reason; never carries image or descriptor data. */
export class ModelLoadError extends Error {
  reason: ModelFailureReason;
  status?: number;
  constructor(reason: ModelFailureReason, message: string, status?: number) {
    super(message);
    this.name = "ModelLoadError";
    this.reason = reason;
    this.status = status;
  }
}

let info: ModelLoadInfo = { state: "idle", phase: "preparing", failureReason: null, cache: "unknown" };
const infoListeners = new Set<() => void>();

function setInfo(patch: Partial<ModelLoadInfo>): void {
  const next = { ...info, ...patch };
  if (
    next.state === info.state && next.phase === info.phase &&
    next.failureReason === info.failureReason && next.cache === info.cache
  ) return;
  info = next; // a new object only when something changed, so useSyncExternalStore snapshots stay stable
  infoListeners.forEach(fn => fn());
}

/** Snapshot of the loader state (a stable object until something changes). */
export function getModelLoadInfo(): ModelLoadInfo {
  return info;
}

export function getModelLoadState(): ModelLoadState {
  return info.state;
}

/** Subscribe to state changes; returns an unsubscribe function. */
export function subscribeModelLoadState(fn: () => void): () => void {
  infoListeners.add(fn);
  return () => { infoListeners.delete(fn); };
}

const cacheTally = { hit: 0, miss: 0 };

function summarizeCache(): ModelCacheStatus {
  if (cacheTally.hit === 0 && cacheTally.miss === 0) return "unknown";
  if (cacheTally.miss === 0) return "hit";
  if (cacheTally.hit === 0) return "miss";
  return "partial";
}

function recordCache(servedFromCache: boolean | undefined): void {
  if (servedFromCache === undefined) return;
  if (servedFromCache) cacheTally.hit += 1; else cacheTally.miss += 1;
  setInfo({ cache: summarizeCache() });
}

/**
 * Whether a weight file was served from the browser cache, from the Resource
 * Timing entry of its fetch: a cached read transfers (almost) no bytes while its
 * decoded body is the full size. Only judged on the big shard files - a tiny
 * JSON manifest is too small for the ratio to mean anything - and "unknown"
 * (undefined) whenever the entry is missing or has no sizes.
 */
function wasServedFromCache(name: string): boolean | undefined {
  if (!name.includes("shard")) return undefined;
  try {
    const url = new URL(`${MODEL_URL}/${name}`, window.location.href).href;
    const entries = performance.getEntriesByName(url, "resource") as PerformanceResourceTiming[];
    const entry = entries[entries.length - 1];
    if (!entry || !(entry.decodedBodySize > 0)) return undefined;
    return entry.transferSize < entry.decodedBodySize * 0.05;
  } catch {
    return undefined;
  }
}

function beginAttemptIfNeeded(): void {
  if (info.state === "loading" || info.state === "ready") return;
  cacheTally.hit = 0;
  cacheTally.miss = 0;
  setInfo({ state: "loading", phase: "preparing", failureReason: null, cache: "unknown" });
}

function markFailed(err: unknown): void {
  const reason: ModelFailureReason = err instanceof ModelLoadError ? err.reason : "init";
  setInfo({ state: "failed", phase: "preparing", failureReason: reason });
}

function refreshReadyState(): void {
  if (detectionReady && recognitionReady) {
    setInfo({ state: "ready", phase: "preparing", failureReason: null });
  }
}

// ─── Loader bookkeeping ───────────────────────────────────────────────────

let detectionPromise: Promise<void> | null = null;
let detectionDownload: Promise<void> | null = null; // stage 1's network part only
let recognitionPromise: Promise<void> | null = null;
let detectionReady = false;
let recognitionReady = false;
let progress = 0; // 0-1, progress of the DETECTION stage - the one the camera start waits for
const listeners = new Set<(p: number) => void>();

function setProgress(p: number): void {
  progress = Math.max(progress, Math.min(1, p)); // never goes backwards
  listeners.forEach(fn => fn(progress));
}

/** Progress of the models needed to START the camera flow, 0-1 (1 once they are loaded and warm). */
export function getModelLoadProgress(): number {
  return progress;
}

/** Subscribe to progress updates; returns an unsubscribe function. */
export function subscribeModelLoadProgress(fn: (p: number) => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

/** True once the detector + landmark models are loaded (enough for framing and liveness). */
export function isDetectionReady(): boolean {
  return detectionReady;
}

/** True once the recognition model is loaded and passed its self-test (needed for the final descriptor). */
export function isRecognitionReady(): boolean {
  return recognitionReady;
}

// ─── Fetching ─────────────────────────────────────────────────────────────

/** The original (pre-V2) behaviour: stream one file for byte progress, no timeout. */
async function legacyPrefetchFile(url: string, name: string, onBytes: (n: number) => void): Promise<void> {
  const res = await fetch(url, { cache: "force-cache" });
  if (!res.ok) throw new Error(`Failed to fetch model file ${name}: ${res.status}`);
  if (!res.body) {
    onBytes(0);
    await res.arrayBuffer();
    return;
  }
  const reader = res.body.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    onBytes(value.byteLength);
  }
}

function toLoadError(err: unknown, aborted: boolean, name: string): ModelLoadError {
  if (err instanceof ModelLoadError) return err;
  if (aborted) {
    return new ModelLoadError("timeout", `Model file ${name} made no progress for ${MODEL_STALL_TIMEOUT_MS / 1000}s`);
  }
  const detail = err instanceof Error ? err.message : "request failed";
  return new ModelLoadError("network", `Failed to fetch model file ${name}: ${detail}`);
}

function isRetriable(err: ModelLoadError): boolean {
  if (err.reason === "timeout" || err.reason === "network") return true;
  return err.reason === "http" && (err.status ?? 0) >= 500;
}

/**
 * Streams one file so byte progress can be reported, and leaves it in the
 * browser HTTP cache (see the /models cache headers in next.config.ts) so the
 * face-api.js loadFromUri() calls below are served locally instead of
 * downloading everything a second time.
 *
 * V2: aborts the request if it makes no progress for MODEL_STALL_TIMEOUT_MS
 * (the timer restarts on every chunk, so a slow-but-moving download is never
 * killed) and retries ONCE on a timeout, network error or 5xx. A 4xx (e.g. a
 * missing file) is deterministic, so it fails immediately.
 */
async function prefetchFile(name: string, onBytes: (n: number) => void, detectionStage: boolean): Promise<void> {
  const url = `${MODEL_URL}/${name}`;
  if (!isFaceLoaderV2()) return legacyPrefetchFile(url, name, onBytes);

  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController();
    let stallTimer: ReturnType<typeof setTimeout> | undefined;
    const armStallTimer = () => {
      clearTimeout(stallTimer);
      stallTimer = setTimeout(() => controller.abort(), MODEL_STALL_TIMEOUT_MS);
    };
    const downloadingTimer = detectionStage
      ? setTimeout(() => setInfo({ phase: "downloading" }), DOWNLOADING_AFTER_MS)
      : undefined;
    try {
      armStallTimer();
      const res = await fetch(url, { cache: "force-cache", signal: controller.signal });
      if (!res.ok) throw new ModelLoadError("http", `Failed to fetch model file ${name}: ${res.status}`, res.status);
      if (!res.body) {
        onBytes(0);
        await res.arrayBuffer();
      } else {
        const reader = res.body.getReader();
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          armStallTimer();
          onBytes(value.byteLength);
        }
      }
      recordCache(wasServedFromCache(name));
      return;
    } catch (err: unknown) {
      const failure = toLoadError(err, controller.signal.aborted, name);
      if (attempt === 0 && isRetriable(failure)) continue; // the finally below still clears this attempt's timers
      throw failure;
    } finally {
      clearTimeout(stallTimer);
      clearTimeout(downloadingTimer);
    }
  }
}

async function prefetchAll(
  files: Record<string, number>, onBytes: (n: number) => void, detectionStage: boolean,
): Promise<void> {
  await Promise.all(Object.keys(files).map(name => prefetchFile(name, onBytes, detectionStage)));
}

// ─── Warm-up and self-test ────────────────────────────────────────────────

function makeWarmupCanvas(size: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    // Not a flat colour: a gradient avoids degenerate-input shortcuts in the first pass.
    const g = ctx.createLinearGradient(0, 0, size, size);
    g.addColorStop(0, "#808080");
    g.addColorStop(1, "#c0c0c0");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
  }
  return canvas;
}

/**
 * Runs each network once on a tiny dummy input. The first inference after load
 * compiles the WebGL shaders (typically 1-3 seconds), which would otherwise be
 * spent while the employee is already standing in front of the camera. Never
 * throws - a failed warm-up only means that cost is paid on first real use.
 */
async function warmUpDetection(): Promise<void> {
  try {
    await faceapi.tinyFaceDetector(makeWarmupCanvas(224), new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 }));
    await faceapi.nets.faceLandmark68Net.detectLandmarks(makeWarmupCanvas(112));
  } catch {
    // Warm-up is an optimisation only.
  }
}

async function warmUpRecognition(): Promise<void> {
  try {
    await faceapi.nets.faceRecognitionNet.computeFaceDescriptor(makeWarmupCanvas(150));
  } catch {
    // Warm-up is an optimisation only.
  }
}

/**
 * V2 replacement for warmUpRecognition: the same one inference on a dummy input
 * (so the shader-compile cost is still paid up front), but its output is now
 * CHECKED - exactly 128 values, all finite. A model that loaded but cannot
 * produce a valid descriptor must not be allowed to start a capture, or every
 * submitted vector would be rejected by the server as a mismatch and count
 * towards the employee's lockout. Only the vector's length is ever reported.
 */
async function selfTestRecognition(): Promise<void> {
  let output: ArrayLike<number>;
  try {
    output = await faceapi.nets.faceRecognitionNet.computeFaceDescriptor(makeWarmupCanvas(150)) as ArrayLike<number>;
  } catch (err: unknown) {
    const detail = err instanceof Error ? err.message : "inference failed";
    throw new ModelLoadError("self_test", `Recognition self-test could not run: ${detail}`);
  }
  if (!isValidDescriptor(output)) {
    const length = output && typeof output.length === "number" ? output.length : "unknown";
    throw new ModelLoadError("self_test", `Recognition self-test produced an invalid descriptor (length ${length})`);
  }
}

// ─── Stages ───────────────────────────────────────────────────────────────

/**
 * Stage 1: detector + landmarks (small). Idempotent - safe to call from every
 * mount; the network fetch happens once per success. On failure the cached
 * promise is cleared so the next call (e.g. the user clicking "Try Again")
 * actually re-issues the request instead of replaying the same rejection for
 * the rest of the tab's life.
 */
export function loadDetectionModels(): Promise<void> {
  if (!detectionPromise) {
    beginAttemptIfNeeded();
    let received = 0;
    const total = Object.values(DETECTION_FILES).reduce((a, b) => a + b, 0);
    const download = prefetchAll(DETECTION_FILES, n => { received += n; setProgress((received / total) * 0.9); }, true)
      .then(() => { setInfo({ phase: "preparing" }); });
    detectionDownload = download;
    detectionPromise = download
      .then(() => Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
      ]))
      .then(() => warmUpDetection())
      .then(() => { detectionReady = true; setProgress(1); refreshReadyState(); })
      .catch((err: unknown) => {
        detectionPromise = null;
        detectionDownload = null;
        progress = 0;
        markFailed(err);
        throw err;
      });
  }
  return detectionPromise;
}

/**
 * Stage 2: the recognition net (large). Idempotent, with the same
 * retry-after-failure behaviour as stage 1.
 *
 * Legacy: starts only AFTER stage 1 has finished completely (including its
 * warm-up), so the network sits idle during that warm-up.
 * V2: the download starts as soon as stage 1's own (tiny) download is in, in
 * parallel with stage 1's load + warm-up. Loading the recognition net and its
 * self-test still wait for stage 1 to finish, so the two never run inference at
 * the same time, and the small stage is never slowed by more than its own
 * 0.55 MB having already finished.
 */
export function loadRecognitionModel(): Promise<void> {
  if (!recognitionPromise) {
    beginAttemptIfNeeded();
    const detection = loadDetectionModels();
    const fail = (err: unknown): never => {
      recognitionPromise = null;
      markFailed(err);
      throw err;
    };
    if (isFaceLoaderV2()) {
      const detectionFilesIn = detectionDownload ?? Promise.resolve();
      const recognitionDownload = detectionFilesIn.then(() => prefetchAll(RECOGNITION_FILES, () => undefined, false));
      recognitionPromise = Promise.all([detection, recognitionDownload])
        .then(() => faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL))
        .then(() => selfTestRecognition())
        .then(() => { recognitionReady = true; refreshReadyState(); })
        .catch(fail);
    } else {
      recognitionPromise = detection
        .then(() => prefetchAll(RECOGNITION_FILES, () => undefined, false))
        .then(() => faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL))
        .then(() => warmUpRecognition())
        .then(() => { recognitionReady = true; refreshReadyState(); })
        .catch(fail);
    }
  }
  return recognitionPromise;
}

/**
 * Both stages. Called ahead of time (see preload.ts) so the models are usually
 * already loaded by the time someone clicks Clock In.
 */
export function loadFaceApiModels(): Promise<void> {
  return Promise.all([loadDetectionModels(), loadRecognitionModel()]).then(() => undefined);
}

/**
 * Explicit retry after a failure. The failed stage's promise was already cleared,
 * so this simply starts a fresh attempt (state goes failed -> loading) without a
 * page reload. Safe to call at any time - while loading or ready it just joins
 * the existing work.
 */
export function retryModelLoad(): Promise<void> {
  return loadFaceApiModels();
}

// ─── Messages ─────────────────────────────────────────────────────────────

const GENERIC_LOAD_FAILURE = "Could not load face-recognition models. Check your connection and try again.";

/** Telemetry code + user-facing message for a model-load failure. Anything but a V2 timeout / self-test keeps the original wording. */
export function describeModelLoadFailure(err: unknown): { code: string; message: string } {
  if (err instanceof ModelLoadError) {
    if (err.reason === "timeout") {
      return { code: "models_timeout", message: "Downloading the face models is taking too long. Check your connection and try again." };
    }
    if (err.reason === "self_test") {
      return { code: "models_self_test_failed", message: "Face verification couldn't start on this device. Please try again." };
    }
  }
  return { code: "models_failed", message: GENERIC_LOAD_FAILURE };
}

/** Loading-screen text that matches what is really happening (V2); the original text when V2 is off. */
export function modelLoadingMessage(phase: ModelLoadPhase): string {
  if (!isFaceLoaderV2()) return "Downloading face models (first time only)…";
  return phase === "downloading" ? "Downloading face verification models…" : "Preparing face verification…";
}

/** Test-only: forget everything so each test starts from a cold loader. */
export function __resetModelLoaderForTests(): void {
  detectionPromise = null;
  detectionDownload = null;
  recognitionPromise = null;
  detectionReady = false;
  recognitionReady = false;
  progress = 0;
  cacheTally.hit = 0;
  cacheTally.miss = 0;
  info = { state: "idle", phase: "preparing", failureReason: null, cache: "unknown" };
}

export { faceapi };
