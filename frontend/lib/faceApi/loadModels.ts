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
import * as faceapi from "face-api.js";

const MODEL_URL = "/models";

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

let detectionPromise: Promise<void> | null = null;
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

/** True once the recognition model is loaded (needed for the final descriptor). */
export function isRecognitionReady(): boolean {
  return recognitionReady;
}

/** Streams one file so byte progress can be reported, and leaves it in the
 *  browser HTTP cache (see the /models cache headers in next.config.ts) so the
 *  face-api.js loadFromUri() calls below are served locally instead of
 *  downloading everything a second time. */
async function prefetchFile(name: string, onBytes: (n: number) => void): Promise<void> {
  const res = await fetch(`${MODEL_URL}/${name}`, { cache: "force-cache" });
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

async function prefetchAll(files: Record<string, number>, onBytes: (n: number) => void): Promise<void> {
  await Promise.all(Object.keys(files).map(name => prefetchFile(name, onBytes)));
}

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
 * Stage 1: detector + landmarks (small). Idempotent - safe to call from every
 * mount; the network fetch happens once per success. On failure the cached
 * promise is cleared so the next call (e.g. the user clicking "Try Again")
 * actually re-issues the request instead of replaying the same rejection for
 * the rest of the tab's life.
 */
export function loadDetectionModels(): Promise<void> {
  if (!detectionPromise) {
    let received = 0;
    const total = Object.values(DETECTION_FILES).reduce((a, b) => a + b, 0);
    detectionPromise = prefetchAll(DETECTION_FILES, n => { received += n; setProgress((received / total) * 0.9); })
      .then(() => Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
      ]))
      .then(() => warmUpDetection())
      .then(() => { detectionReady = true; setProgress(1); })
      .catch((err) => {
        detectionPromise = null;
        progress = 0;
        throw err;
      });
  }
  return detectionPromise;
}

/**
 * Stage 2: the recognition net (large). Always starts AFTER stage 1 has
 * finished so the small models are never slowed down by the big download.
 * Idempotent, with the same retry-after-failure behaviour as stage 1.
 */
export function loadRecognitionModel(): Promise<void> {
  if (!recognitionPromise) {
    recognitionPromise = loadDetectionModels()
      .then(() => prefetchAll(RECOGNITION_FILES, () => undefined))
      .then(() => faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL))
      .then(() => warmUpRecognition())
      .then(() => { recognitionReady = true; })
      .catch((err) => {
        recognitionPromise = null;
        throw err;
      });
  }
  return recognitionPromise;
}

/**
 * Both stages. Called ahead of time (from FaceModelPreloader / the clock widget)
 * so the models are usually already loaded by the time someone clicks Clock In.
 */
export function loadFaceApiModels(): Promise<void> {
  return Promise.all([loadDetectionModels(), loadRecognitionModel()]).then(() => undefined);
}

export { faceapi };
