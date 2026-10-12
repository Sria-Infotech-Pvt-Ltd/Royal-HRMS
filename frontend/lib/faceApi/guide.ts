// The dotted guide oval drawn over the camera preview ("keep your face inside
// the dotted frame") and the check that the detected face is actually in it.
// Guiding people to one spot makes their distance consistent, so the face has
// enough real pixels for recognition without anyone having to guess how close
// to stand. Pure functions — testable in plain Node.

/** Oval size as a fraction of the preview's width/height (the same numbers the stage draws). */
export const GUIDE = { widthFraction: 0.44, heightFraction: 0.8 } as const;

/** The preview container is 4:3 (see FaceCaptureStage) and the video fills it with object-fit: cover. */
const STAGE_ASPECT = 4 / 3;

/**
 * True when the centre of the face box lies inside the guide oval. `box` and
 * `video` share the video's native pixel space; the cover-crop of a non-4:3
 * camera (e.g. 16:9) is accounted for, so "inside the oval on screen" and
 * "inside the oval here" agree.
 */
export function faceInsideGuide(
  box: { x: number; y: number; width: number; height: number },
  video: { width: number; height: number },
): boolean {
  if (video.width <= 0 || video.height <= 0) return true; // nothing to judge yet — never block on it
  const videoAspect = video.width / video.height;
  const visibleW = videoAspect > STAGE_ASPECT ? STAGE_ASPECT / videoAspect : 1;
  const visibleH = videoAspect < STAGE_ASPECT ? videoAspect / STAGE_ASPECT : 1;

  const cx = 0.5 + ((box.x + box.width / 2) / video.width - 0.5) / visibleW;
  const cy = 0.5 + ((box.y + box.height / 2) / video.height - 0.5) / visibleH;
  const nx = (cx - 0.5) / (GUIDE.widthFraction / 2);
  const ny = (cy - 0.5) / (GUIDE.heightFraction / 2);
  return nx * nx + ny * ny <= 1;
}
