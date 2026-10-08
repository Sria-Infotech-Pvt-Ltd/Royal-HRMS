// Loads the three face-api.js models the registration flow needs, from the
// self-hosted weights in public/models/ (see public/models/README.md for
// provenance — pinned to a specific face-api.js commit, not a CDN).
//
//   tinyFaceDetector   — locates the face in each video frame (fast enough
//                        to run every frame for the live preview + liveness
//                        tracking).
//   faceLandmark68Net  — the 68-point landmark map used for the liveness
//                        check (eye/nose position tracking across frames).
//   faceRecognitionNet — generates the 128-d descriptor that becomes
//                        face_embedding. Its identity is exactly what the
//                        backend's FACE_RECOGNITION_MODEL_VERSION constant
//                        ('face-api.js-faceRecognitionNet-v1') pins the
//                        stored vector space to — never swap this model
//                        without also changing that backend constant.
import * as faceapi from "face-api.js";

const MODEL_URL = "/models";

// Approximate byte sizes of the seven files in public/models/ — only used to
// turn "bytes received so far" into a 0–1 progress fraction for the loading
// UI, so being a little off is harmless. Keep the filenames in sync with that folder.
const MODEL_FILES: Record<string, number> = {
  "tiny_face_detector_model-weights_manifest.json": 3_000,
  "tiny_face_detector_model-shard1": 193_321,
  "face_landmark_68_model-weights_manifest.json": 8_000,
  "face_landmark_68_model-shard1": 356_840,
  "face_recognition_model-weights_manifest.json": 18_500,
  "face_recognition_model-shard1": 4_194_304,
  "face_recognition_model-shard2": 2_249_728,
};
const TOTAL_BYTES = Object.values(MODEL_FILES).reduce((a, b) => a + b, 0);

let modelsPromise: Promise<void> | null = null;
let progress = 0; // 0–1
const listeners = new Set<(p: number) => void>();

function setProgress(p: number): void {
  progress = Math.max(progress, Math.min(1, p)); // never goes backwards
  listeners.forEach(fn => fn(progress));
}

/** Current model-download progress, 0–1 (1 once everything is loaded). */
export function getModelLoadProgress(): number {
  return progress;
}

/** Subscribe to progress updates; returns an unsubscribe function. */
export function subscribeModelLoadProgress(fn: (p: number) => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

/** Streams one file so byte progress can be reported, and leaves it in the
 *  browser HTTP cache (see the /models cache headers in next.config.ts) so the
 *  face-api.js loadFromUri() calls below are served locally instead of
 *  downloading everything a second time. */
async function prefetchFile(name: string, onBytes: (n: number) => void): Promise<void> {
  const res = await fetch(`${MODEL_URL}/${name}`, { cache: "force-cache" });
  if (!res.ok) throw new Error(`Failed to fetch model file ${name}: ${res.status}`);
  if (!res.body) {
    onBytes(MODEL_FILES[name]);
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

async function prefetchAll(): Promise<void> {
  let received = 0;
  // 0.95 cap: the last 5% is face-api.js parsing the weights into tensors.
  const onBytes = (n: number) => { received += n; setProgress((received / TOTAL_BYTES) * 0.95); };
  await Promise.all(Object.keys(MODEL_FILES).map(name => prefetchFile(name, onBytes)));
}

/**
 * Runs each network once on a tiny dummy input. The first inference after load
 * compiles the WebGL shaders (typically 1-3 seconds), which would otherwise be
 * spent while the employee is already standing in front of the camera. Never
 * throws — a failed warm-up only means that cost is paid on first real use.
 */
async function warmUpModels(): Promise<void> {
  try {
    const make = (size: number) => {
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
    };
    await faceapi.tinyFaceDetector(make(224), new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 }));
    await faceapi.nets.faceLandmark68Net.detectLandmarks(make(112));
    await faceapi.nets.faceRecognitionNet.computeFaceDescriptor(make(150));
  } catch {
    // Warm-up is an optimisation only.
  }
}

/**
 * Idempotent — safe to call from every mount; the network fetch happens once
 * per success. On failure the cached promise is cleared so the next call
 * (e.g. the user clicking "Try Again") actually re-issues the network
 * request instead of replaying the same rejection forever for the rest of
 * the tab's life.
 *
 * Also called ahead of time (idle, when the clock widget mounts) so the
 * models are usually already loaded by the time someone clicks Clock In.
 */
export function loadFaceApiModels(): Promise<void> {
  if (!modelsPromise) {
    modelsPromise = prefetchAll()
      .then(() => Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
        faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
      ]))
      .then(() => warmUpModels())
      .then(() => { setProgress(1); })
      .catch((err) => {
        modelsPromise = null;
        progress = 0;
        throw err;
      });
  }
  return modelsPromise;
}

export { faceapi };
