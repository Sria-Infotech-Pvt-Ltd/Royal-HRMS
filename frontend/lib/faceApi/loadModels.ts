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

let modelsPromise: Promise<void> | null = null;

/**
 * Idempotent — safe to call from every mount; the network fetch happens once
 * per success. On failure the cached promise is cleared so the next call
 * (e.g. the user clicking "Try Again") actually re-issues the network
 * request instead of replaying the same rejection forever for the rest of
 * the tab's life.
 */
export function loadFaceApiModels(): Promise<void> {
  if (!modelsPromise) {
    modelsPromise = Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
      faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
      faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
    ])
      .then(() => undefined)
      .catch((err) => {
        modelsPromise = null;
        throw err;
      });
  }
  return modelsPromise;
}

export { faceapi };
