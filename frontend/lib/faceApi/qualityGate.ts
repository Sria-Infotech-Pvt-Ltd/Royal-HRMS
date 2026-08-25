// Registration-time capture quality gate — the direct fix for the mismatch
// bug's root cause: an employee's registered reference embedding whose own
// historical match distances already sat at ~0.51-0.55, barely under
// FACE_MATCH_MAX_DISTANCE (0.6), leaving almost no margin to reject an
// impostor. That reference came from a single accepted frame with no check
// on lighting, angle, distance from camera, or detector confidence.
//
// This module scores each candidate frame against concrete, measurable
// signals face-api.js already gives us (detector confidence, bounding box,
// landmark positions) and rejects frames that don't clear a minimum bar —
// see multiFrameCapture.ts for how rejected frames trigger a retry instead
// of ever reaching face_embedding.
//
// Pure functions, no face-api.js/DOM dependency — testable in plain Node.

export interface FrameQualityMetrics {
  /** face-api.js TinyFaceDetector's own confidence for this detection, 0-1. */
  detectionScore: number;
  /** Face bounding-box width / video frame width — too small means "too far
   *  from the camera" (few pixels of actual face detail to work with); too
   *  large usually means edge-clipping or an unnaturally close/distorted shot. */
  faceWidthRatio: number;
  /** How front-facing the pose is, 0-1 (1 = perfectly frontal) — see
   *  computeFrontality below. A turned head feeds the recognition net an
   *  asymmetric view it wasn't primarily trained to align well. */
  frontality: number;
  /** Mean luminance (0-255) of the face bounding box — catches frames that
   *  are still too dark/blown-out even after CLAHE normalization (CLAHE
   *  improves LOCAL contrast; it can't invent detail that was never
   *  captured in a badly underexposed sensor read). */
  meanLuminance: number;
}

export interface QualityGateResult {
  passed: boolean;
  /** Empty when passed — human-readable reasons otherwise, e.g. shown to
   *  the employee as "move closer" / "face the camera directly". */
  reasons: string[];
  metrics: FrameQualityMetrics;
}

// Every threshold below is a judgment call, not a physical constant — named
// and commented individually so they're easy to retune against real
// registration data later without hunting through the assessment logic.
export const QUALITY_THRESHOLDS = {
  /** Below this, the detector itself isn't confident this is a face at all
   *  (motion blur, partial occlusion, bad angle) — no point extracting a
   *  descriptor from a shaky detection. */
  MIN_DETECTION_SCORE: 0.8,
  /** Face narrower than 20% of frame width reads as "too far away" — too few
   *  pixels across the face for the descriptor to be reliable. */
  MIN_FACE_WIDTH_RATIO: 0.20,
  /** Wider than 75% usually means the face is clipped at the frame edge or
   *  the camera is uncomfortably close, both of which distort the crop
   *  face-api.js's alignment step feeds to the recognition net. */
  MAX_FACE_WIDTH_RATIO: 0.75,
  /** Below this frontality, the pose is turned enough that dlib-style
   *  alignment (see FaceRecognitionNet's use of landmarks.align()) is
   *  working from a meaningfully asymmetric face. */
  MIN_FRONTALITY: 0.7,
  /** Luminance floor/ceiling (0-255 scale) — well outside typical
   *  "adequately lit indoor face" range even after CLAHE. */
  MIN_MEAN_LUMINANCE: 60,
  MAX_MEAN_LUMINANCE: 200,
} as const;

export function assessFrameQuality(metrics: FrameQualityMetrics): QualityGateResult {
  const reasons: string[] = [];

  if (metrics.detectionScore < QUALITY_THRESHOLDS.MIN_DETECTION_SCORE) {
    reasons.push('Face detection confidence too low — hold still and make sure your face is unobstructed.');
  }
  if (metrics.faceWidthRatio < QUALITY_THRESHOLDS.MIN_FACE_WIDTH_RATIO) {
    reasons.push('Face too far from the camera — move closer.');
  }
  if (metrics.faceWidthRatio > QUALITY_THRESHOLDS.MAX_FACE_WIDTH_RATIO) {
    reasons.push('Face too close to the camera — move back a little.');
  }
  if (metrics.frontality < QUALITY_THRESHOLDS.MIN_FRONTALITY) {
    reasons.push('Face not centered/frontal enough — look directly at the camera.');
  }
  if (metrics.meanLuminance < QUALITY_THRESHOLDS.MIN_MEAN_LUMINANCE) {
    reasons.push('Lighting too dark — move to a better-lit area.');
  }
  if (metrics.meanLuminance > QUALITY_THRESHOLDS.MAX_MEAN_LUMINANCE) {
    reasons.push('Lighting too bright/overexposed — avoid direct backlight or glare.');
  }

  return { passed: reasons.length === 0, reasons, metrics };
}

interface Point { x: number; y: number }

/**
 * 0-1 pose-frontality heuristic from 68-point landmarks alone (face-api.js
 * doesn't expose yaw/pitch/roll directly). Compares the nose tip's distance
 * to each eye's center — for a frontal face these are nearly equal; turning
 * the head lengthens one side and shortens the other. Normalized by
 * inter-eye distance so it doesn't depend on how close the camera is.
 */
export function computeFrontality(leftEye: Point[], rightEye: Point[], noseTip: Point): number {
  const leftCenter = centerOf(leftEye);
  const rightCenter = centerOf(rightEye);
  const interEyeWidth = distance(leftCenter, rightCenter);
  if (interEyeWidth === 0) return 0;

  const leftDist = distance(leftCenter, noseTip);
  const rightDist = distance(rightCenter, noseTip);
  const asymmetry = Math.abs(leftDist - rightDist) / interEyeWidth;
  // An asymmetry of ~0.5x the inter-eye width is already a substantial turn —
  // scale so that lands near 0, and keep the result clamped to [0, 1].
  return Math.max(0, Math.min(1, 1 - asymmetry / 0.5));
}

function centerOf(points: Point[]): Point {
  const sum = points.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), { x: 0, y: 0 });
  return { x: sum.x / points.length, y: sum.y / points.length };
}

function distance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

// ─── Multi-frame consistency + averaging ───────────────────────────────────

export interface ConsistencyResult {
  passed: boolean;
  meanPairwiseDistance: number;
  maxPairwiseDistance: number;
}

/**
 * A "good enough per-frame" set can still disagree with itself — e.g. the
 * person shifted mid-capture, or lighting flickered between frames. Rather
 * than silently averaging noisy frames into a mediocre composite, this
 * checks the frames actually agree with EACH OTHER before they're trusted
 * enough to average — see multiFrameCapture.ts for what happens when they don't.
 */
export function assessCaptureConsistency(descriptors: number[][], maxAllowedDistance: number): ConsistencyResult {
  const pairwiseDistances: number[] = [];
  for (let i = 0; i < descriptors.length; i++) {
    for (let j = i + 1; j < descriptors.length; j++) {
      pairwiseDistances.push(euclideanDistance(descriptors[i], descriptors[j]));
    }
  }
  if (pairwiseDistances.length === 0) {
    // A single frame has nothing to compare against — treated as
    // consistent by definition (there's no multi-frame benefit to gate on),
    // but callers should still prefer requiring framesToCapture > 1.
    return { passed: true, meanPairwiseDistance: 0, maxPairwiseDistance: 0 };
  }

  const meanPairwiseDistance = pairwiseDistances.reduce((a, b) => a + b, 0) / pairwiseDistances.length;
  const maxPairwiseDistance = Math.max(...pairwiseDistances);
  return { passed: maxPairwiseDistance <= maxAllowedDistance, meanPairwiseDistance, maxPairwiseDistance };
}

/** Element-wise mean of N same-length descriptors — the composite reference
 *  embedding stored as face_embedding once consistency passes. */
export function averageDescriptors(descriptors: number[][]): number[] {
  if (descriptors.length === 0) throw new Error('averageDescriptors: need at least one descriptor.');
  const length = descriptors[0].length;
  const sums = new Array(length).fill(0);
  for (const descriptor of descriptors) {
    if (descriptor.length !== length) {
      throw new Error('averageDescriptors: all descriptors must have the same length.');
    }
    for (let i = 0; i < length; i++) sums[i] += descriptor[i];
  }
  return sums.map(sum => sum / descriptors.length);
}

export function euclideanDistance(a: number[], b: number[]): number {
  if (a.length !== b.length) throw new Error('euclideanDistance: length mismatch.');
  let sumSquares = 0;
  for (let i = 0; i < a.length; i++) {
    const diff = a[i] - b[i];
    sumSquares += diff * diff;
  }
  return Math.sqrt(sumSquares);
}

// ─── Failure messages beyond the per-frame quality gate ────────────────────
// assessFrameQuality's own `reasons` above already double as user-facing
// copy for its 6 checks (distinct and polite as written — see the FR-1 audit
// this responds to). These two cover the two capture-time failures that
// aren't part of that gate: more than one face in frame, and a best-effort
// guess that the eyes are covered (see frameCapture.ts's assessEyeOcclusion
// for the actual signal). Named as constants, not inlined, so every caller
// that needs to recognize "this specific message" (tests included) has one
// place to reference instead of a repeated string literal.
export const MULTIPLE_FACES_MESSAGE =
  'Multiple faces detected — please make sure only your face is in frame.';
export const EYE_OCCLUSION_MESSAGE =
  "We couldn't clearly detect your eyes — please remove sunglasses or anything covering your face and try again.";

export type DetectedFaceCount = 'none' | 'single' | 'multiple';

/**
 * What a detectAllFaces() call's result count means for a capture attempt —
 * pulled out of useFaceLivenessCapture.ts's captureOneQualityGatedFrame as
 * its own pure function so "0 faces retries silently, exactly 1 face
 * proceeds to the quality gate, more than 1 face is rejected with
 * MULTIPLE_FACES_MESSAGE" is unit-testable without mocking face-api.js, the
 * camera, or the DOM.
 */
export function classifyDetectedFaceCount(count: number): DetectedFaceCount {
  if (count === 0) return 'none';
  if (count === 1) return 'single';
  return 'multiple';
}

/**
 * A quality-gated multi-frame capture can fail several attempts in a row for
 * DIFFERENT reasons (a shadow passes, then the person turns their head) —
 * picking any single attempt's reason arbitrarily would be misleading, and
 * showing all of them at once would read as a wall of text. This takes the
 * most RECENT attempt that had a specific, identifiable reason (as opposed
 * to "no face detected this instant", which isn't attributable to anything
 * the person can act on) — the most recent read of conditions is the most
 * relevant one by the time the whole capture gives up and surfaces a
 * message. Returns null when no attempt ever produced a specific reason
 * (e.g. a face was never detected at all), so the caller can fall back to
 * its own generic message instead of showing nothing.
 */
export function selectFailureMessage(reasonsPerAttempt: string[][]): string | null {
  let lastReason: string | null = null;
  for (const reasons of reasonsPerAttempt) {
    if (reasons.length > 0) lastReason = reasons[0];
  }
  return lastReason;
}
