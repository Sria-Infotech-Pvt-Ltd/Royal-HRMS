// Offscreen video-frame capture for multi-frame registration captures.
// Distinct from overlay.ts's canvas, which is the VISIBLE detection-box
// overlay sized to the video's displayed CSS size — this works in the
// video's NATIVE pixel resolution (videoWidth/videoHeight), matching what
// face-api.js's detector reads when given the video element directly (the
// existing single-frame/punch-time path). CLAHE-normalizing THIS canvas and
// handing it to face-api.js instead of the raw video element produces a
// like-for-like detection, just on a lighting-corrected frame.
import type { PixelBuffer } from './clahe';

/** Draws the video's current frame into `workingCanvas` (resized to match
 *  the video's native resolution if needed) and returns its pixel data. */
export function grabVideoFrame(video: HTMLVideoElement, workingCanvas: HTMLCanvasElement): ImageData {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (width === 0 || height === 0) {
    throw new Error('grabVideoFrame: video has no dimensions yet.');
  }
  if (workingCanvas.width !== width) workingCanvas.width = width;
  if (workingCanvas.height !== height) workingCanvas.height = height;

  // willReadFrequently hints the browser to keep this canvas on a
  // software-readback-friendly path — this canvas is getImageData()'d on
  // every captured frame, unlike overlay.ts's canvas which is write-only.
  const ctx = workingCanvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('grabVideoFrame: 2D canvas context unavailable.');
  ctx.drawImage(video, 0, 0, width, height);
  return ctx.getImageData(0, 0, width, height);
}

/** Writes normalized pixel data back onto the same canvas it came from, so
 *  face-api.js's detector reads the CLAHE-corrected version. */
export function putImageData(workingCanvas: HTMLCanvasElement, imageData: ImageData): void {
  const ctx = workingCanvas.getContext('2d');
  ctx?.putImageData(imageData, 0, 0);
}

/** Mean luminance (ITU-R BT.601) over a bounding box within `imageData` —
 *  the raw brightness signal qualityGate.ts's meanLuminance metric needs.
 *  Box coordinates are clamped to the image's bounds so a detection box
 *  that slightly overhangs an edge doesn't throw. */
export function meanLuminanceOfBox(
  imageData: ImageData, box: { x: number; y: number; width: number; height: number },
): number {
  const x0 = Math.max(0, Math.floor(box.x));
  const y0 = Math.max(0, Math.floor(box.y));
  const x1 = Math.min(imageData.width, Math.ceil(box.x + box.width));
  const y1 = Math.min(imageData.height, Math.ceil(box.y + box.height));
  if (x1 <= x0 || y1 <= y0) return 0;

  let sum = 0;
  let count = 0;
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      const p = (y * imageData.width + x) * 4;
      sum += 0.299 * imageData.data[p] + 0.587 * imageData.data[p + 1] + 0.114 * imageData.data[p + 2];
      count += 1;
    }
  }
  return count === 0 ? 0 : sum / count;
}

// ─── Best-effort eye-occlusion (sunglasses/obstruction) heuristic ─────────
// face-api.js 0.22.2 exposes landmark POSITIONS only — no per-landmark or
// per-region confidence/visibility score exists to read a "the eyes are
// covered" signal directly off. This approximates one from pixel content
// alone: a real, visible open eye has real internal contrast (sclera vs
// iris vs pupil vs skin/lash), even in the mixed lighting this app
// realistically sees, while a dark or mirrored lens reads as comparatively
// flat and dark over that same small region. Neither property alone is
// reliable (eye-socket shadow can be dark without being flat; a washed-out
// frame can be flat without being dark) — both together, on BOTH eyes, is
// the conservative combination this is deliberately tuned around; see each
// constant below and assessEyeOcclusion's own docstring for why.
interface PixelStats {
  mean: number;
  stdDev: number;
}

interface Point { x: number; y: number }

/** Same box-sampling shape as meanLuminanceOfBox, but also returns the
 *  standard deviation of per-pixel luminance in the box — the extra signal
 *  assessEyeOcclusion needs that a mean alone can't provide (a uniformly
 *  flat region reads very differently from a visually complex real eye,
 *  even at the same average brightness). */
function luminanceStatsOfBox(
  imageData: PixelBuffer, box: { x: number; y: number; width: number; height: number },
): PixelStats {
  const x0 = Math.max(0, Math.floor(box.x));
  const y0 = Math.max(0, Math.floor(box.y));
  const x1 = Math.min(imageData.width, Math.ceil(box.x + box.width));
  const y1 = Math.min(imageData.height, Math.ceil(box.y + box.height));
  if (x1 <= x0 || y1 <= y0) return { mean: 0, stdDev: 0 };

  let sum = 0;
  let sumSquares = 0;
  let count = 0;
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      const p = (y * imageData.width + x) * 4;
      const luminance = 0.299 * imageData.data[p] + 0.587 * imageData.data[p + 1] + 0.114 * imageData.data[p + 2];
      sum += luminance;
      sumSquares += luminance * luminance;
      count += 1;
    }
  }
  const mean = sum / count;
  // max(0, ...) guards against a tiny negative from floating-point rounding
  // when the region is (near-)perfectly uniform, which would otherwise feed
  // Math.sqrt a negative number.
  const variance = Math.max(0, sumSquares / count - mean * mean);
  return { mean, stdDev: Math.sqrt(variance) };
}

function boundingBoxOfPoints(points: Point[]): { x: number; y: number; width: number; height: number } {
  const xs = points.map(p => p.x);
  const ys = points.map(p => p.y);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y };
}

export interface EyeOcclusionResult {
  suspected: boolean;
  left: PixelStats;
  right: PixelStats;
}

// Deliberately conservative — see this module's header comment. Both
// thresholds are well below what a legitimate, already-passing frame should
// ever produce: by construction (see useFaceLivenessCapture.ts's call
// order) this only runs once assessFrameQuality has ALREADY accepted the
// frame's overall confidence/distance/frontality/luminance, so a real face
// here is already known to be adequately and evenly lit overall — an eye
// region that's STILL this dark and this flat despite that is a genuine
// anomaly, not just "the room was dim". Preferring under-triggering over
// over-triggering here is a deliberate product choice (see task docs): a
// real user in dim-but-legitimate conditions should never be told to
// "remove sunglasses" they aren't wearing.
const EYE_OCCLUSION_MAX_LUMINANCE = 50; // 0-255; well under qualityGate's own 60 floor for the whole face
const EYE_OCCLUSION_MAX_STD_DEV = 10;   // a real, visible open eye reliably shows more internal contrast than this

/**
 * Best-effort guess at whether the eyes are covered (sunglasses, a mask
 * pulled up too high, a hand, ...) — not a dedicated occlusion detector,
 * since face-api.js doesn't expose one. Requires BOTH eye regions to read
 * as dark-and-flat, not just one: a single occluded-looking eye is more
 * likely an artifact of angled lighting, hair, or motion blur on one side
 * than a genuine obstruction, and a real obstruction (sunglasses) covers
 * both eyes symmetrically anyway. This AND-of-both-signals-on-both-eyes
 * shape is what keeps the heuristic conservative.
 */
export function assessEyeOcclusion(
  imageData: PixelBuffer, leftEye: Point[], rightEye: Point[],
): EyeOcclusionResult {
  const left = luminanceStatsOfBox(imageData, boundingBoxOfPoints(leftEye));
  const right = luminanceStatsOfBox(imageData, boundingBoxOfPoints(rightEye));
  const looksOccluded = (stats: PixelStats) =>
    stats.mean < EYE_OCCLUSION_MAX_LUMINANCE && stats.stdDev < EYE_OCCLUSION_MAX_STD_DEV;
  return { suspected: looksOccluded(left) && looksOccluded(right), left, right };
}
