// Draws the live face-detection box onto a <canvas> stacked over the
// preview <video>. Kept as direct canvas drawing (not React state) because
// it runs once per animation frame — routing that through React state would
// mean a re-render on every frame for no benefit.

export interface DetectionBox {
  x:      number;
  y:      number;
  width:  number;
  height: number;
}

/** Box color communicates phase at a glance: framing → checking → confirmed. */
export const OVERLAY_COLOR = {
  detecting: "#60a5fa", // blue  — face found, framing
  checking:  "#f59e0b", // amber — liveness challenge in progress
  passed:    "#22c55e", // green — liveness passed, about to submit
} as const;

/** Keeps the canvas's pixel size matched to the video's rendered size. */
export function syncCanvasSize(canvas: HTMLCanvasElement, video: HTMLVideoElement): void {
  if (canvas.width !== video.clientWidth || canvas.height !== video.clientHeight) {
    canvas.width  = video.clientWidth;
    canvas.height = video.clientHeight;
  }
}

export function clearOverlay(canvas: HTMLCanvasElement): void {
  const ctx = canvas.getContext("2d");
  ctx?.clearRect(0, 0, canvas.width, canvas.height);
}

/**
 * `box` and `videoNativeSize` are in the video's native pixel space
 * (face-api.js detects against `video.videoWidth`/`videoHeight`); this
 * scales that box into the canvas's displayed (CSS) pixel space, since the
 * preview is typically stretched/letterboxed to fit its container.
 */
export function drawDetectionBox(
  canvas: HTMLCanvasElement,
  box: DetectionBox,
  videoNativeSize: { width: number; height: number },
  color: string,
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx || videoNativeSize.width === 0 || videoNativeSize.height === 0) return;

  const scaleX = canvas.width  / videoNativeSize.width;
  const scaleY = canvas.height / videoNativeSize.height;

  clearOverlay(canvas);
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.roundRect(box.x * scaleX, box.y * scaleY, box.width * scaleX, box.height * scaleY, 12);
  ctx.stroke();
}
