// Live "are you ready to be captured?" assessment, run on the live preview
// BEFORE the liveness challenge starts, so framing/lighting problems are
// told to the employee immediately instead of surfacing only after a full
// liveness + multi-frame capture cycle has already failed.
//
// Pure functions (no DOM / face-api.js) — testable in plain Node.
//
// Only geometry BLOCKS (too far, too close, not frontal): those are exactly
// the conditions the post-liveness quality gate (qualityGate.ts) would reject
// anyway, using the same thresholds. Lighting and detector confidence only
// produce hints — their final judgement is made on the CLAHE-normalized frame
// at capture time, which this raw-preview check cannot reproduce, so blocking
// on them here could wrongly stop someone the real gate would accept.
import { QUALITY_THRESHOLDS } from "./qualityGate";

export type ReadinessCode =
  | "too_far" | "too_close" | "not_frontal" | "backlit" | "too_dark" | "low_confidence";

export interface LiveReadinessInput {
  /** Face box width / video native width. */
  faceWidthRatio: number;
  /** 0-1, see computeFrontality in qualityGate.ts. */
  frontality: number;
  /** Detector confidence, 0-1. */
  detectionScore: number;
  /** Mean luminance of the face box on the raw (un-normalized) preview, 0-255; null if not sampled yet. */
  faceLuminance: number | null;
  /** Mean luminance of the whole frame, 0-255; null if not sampled yet. */
  frameLuminance: number | null;
}

export interface LiveReadiness {
  /** True when no BLOCKING geometry problem exists. */
  ready: boolean;
  code: ReadinessCode | null;
  hint: string | null;
  /** The face is dim on the raw preview — the cue to turn on the screen fill light. */
  lowLight: boolean;
  /** Face much darker than the scene behind it (window/lamp behind the person). */
  backlit: boolean;
}

/** Raw-preview luminance below this is "genuinely dark" — deliberately below
 *  the capture gate's 60 floor because that gate measures AFTER CLAHE lifts dim frames. */
export const RAW_DARK_LUMINANCE = 50;
/** Frame brighter than the face by this much (and face not bright) reads as backlighting. */
export const BACKLIT_DELTA = 50;
export const BACKLIT_MAX_FACE_LUMINANCE = 95;

export const READINESS_HINTS: Record<ReadinessCode, string> = {
  too_far:        "Move a little closer to the camera",
  too_close:      "Move back a little",
  not_frontal:    "Look straight at the camera",
  backlit:        "Light is behind you — turn to face the light",
  too_dark:       "Too dark — face a light or raise your screen brightness",
  low_confidence: "Hold still and keep your face uncovered",
};

export function assessLiveReadiness(input: LiveReadinessInput): LiveReadiness {
  const { faceLuminance, frameLuminance } = input;

  const lowLight = faceLuminance !== null && faceLuminance < RAW_DARK_LUMINANCE;
  const backlit =
    faceLuminance !== null && frameLuminance !== null &&
    faceLuminance < BACKLIT_MAX_FACE_LUMINANCE && frameLuminance - faceLuminance > BACKLIT_DELTA;

  let code: ReadinessCode | null = null;
  let ready = true;
  if (input.faceWidthRatio < QUALITY_THRESHOLDS.MIN_FACE_WIDTH_RATIO) { code = "too_far"; ready = false; }
  else if (input.faceWidthRatio > QUALITY_THRESHOLDS.MAX_FACE_WIDTH_RATIO) { code = "too_close"; ready = false; }
  else if (input.frontality < QUALITY_THRESHOLDS.MIN_FRONTALITY) { code = "not_frontal"; ready = false; }
  else if (backlit) code = "backlit";
  else if (lowLight) code = "too_dark";
  else if (input.detectionScore < QUALITY_THRESHOLDS.MIN_DETECTION_SCORE) code = "low_confidence";

  return { ready, code, hint: code ? READINESS_HINTS[code] : null, lowLight, backlit };
}
