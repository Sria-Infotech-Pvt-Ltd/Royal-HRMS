// Offscreen video-frame capture for multi-frame registration captures.
// Distinct from overlay.ts's canvas, which is the VISIBLE detection-box
// overlay sized to the video's displayed CSS size — this works in the
// video's NATIVE pixel resolution (videoWidth/videoHeight), matching what
// face-api.js's detector reads when given the video element directly (the
// existing single-frame/punch-time path). CLAHE-normalizing THIS canvas and
// handing it to face-api.js instead of the raw video element produces a
// like-for-like detection, just on a lighting-corrected frame.

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
