// Gradual, closed-loop camera brightness for dim rooms.
//
// A website cannot change the device's SCREEN brightness, but many cameras
// expose `exposureCompensation` and/or `brightness` as track constraints
// (Chrome on Windows/Android for most webcams). When the live face reads dim,
// this nudges that control up in small steps — one step per call, so the
// picture brightens smoothly instead of jumping — and stops as soon as the
// face reaches a healthy level or the safe upper limit. The caller restores the
// original value when the camera closes (UVC drivers can otherwise keep it).
//
// Pure functions (no DOM) — testable in plain Node.

export interface RangeCaps { min: number; max: number; step?: number }
export interface BoostCaps { exposureCompensation?: RangeCaps; brightness?: RangeCaps }
export type BoostControl = "exposureCompensation" | "brightness";

/** Face luminance (0-255, raw preview) the boost aims for — comfortably inside
 *  the capture gate's 60-200 window without pushing toward over-exposure. */
export const TARGET_FACE_LUMINANCE = 115;
/** Do nothing unless the face is at least this far below target (avoids hunting around the target). */
export const BOOST_MIN_GAP = 15;
/** Fraction of each step relative to the control's full range — small on purpose, so the change is gradual. */
export const BOOST_STEP_FRACTION = 0.1;
/** Never push past this fraction of the control's range — leaves headroom against blow-out. */
export const BOOST_MAX_FRACTION = 0.85;

export function pickBoostControl(caps: BoostCaps | undefined): { control: BoostControl; range: RangeCaps } | null {
  if (!caps) return null;
  const valid = (r?: RangeCaps): r is RangeCaps =>
    !!r && Number.isFinite(r.min) && Number.isFinite(r.max) && r.max > r.min;
  if (valid(caps.exposureCompensation)) return { control: "exposureCompensation", range: caps.exposureCompensation };
  if (valid(caps.brightness)) return { control: "brightness", range: caps.brightness };
  return null;
}

/** Highest value this boost is allowed to set for a control. */
export function boostLimit(range: RangeCaps): number {
  return range.min + (range.max - range.min) * BOOST_MAX_FRACTION;
}

/**
 * The next (slightly higher) value to apply, or null when no change is needed:
 * the face is already bright enough, or the safe limit has been reached.
 * Snaps to the control's own `step` when it declares one.
 */
export function nextBoostValue(current: number, range: RangeCaps, faceLuminance: number): number | null {
  if (faceLuminance >= TARGET_FACE_LUMINANCE - BOOST_MIN_GAP) return null;
  const limit = boostLimit(range);
  if (current >= limit) return null;

  let next = current + (range.max - range.min) * BOOST_STEP_FRACTION;
  if (range.step && range.step > 0) {
    next = range.min + Math.ceil((next - range.min) / range.step) * range.step;
  }
  next = Math.min(next, limit);
  return next > current ? next : null;
}
