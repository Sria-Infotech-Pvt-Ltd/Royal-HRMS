// Liveness detection: proves the camera is looking at a live person, not a
// static photo held up to it, by tracking real movement across frames — a
// natural blink AND a slight head turn both have to be observed. A single
// still frame can never pass this; it requires landmark positions to
// actually change over a short window of time.
//
// Two independent signals are tracked, and BOTH are required (see
// getResult()):
//   1. Blink  — Eye Aspect Ratio (Soukupová & Čech) dipping and recovering.
//   2. Head turn — the nose tip shifting laterally relative to the eyes.
// Both are normalized against the detected face's own size, so thresholds
// don't depend on how close the camera is.
//
// Requiring only ONE of the two used to be enough (2026-09 QA finding:
// FR-E-18 — a static photo held up to the camera and tilted/rotated during
// the capture window reproduces a head turn's landmark-position delta just
// as well as a real head does, with zero genuine 3D motion involved, so
// "either signal passes" was trivially defeated by a printed or on-screen
// photo). A held photo cannot blink — its eye landmarks don't independently
// dip and recover the way an eyelid does — so requiring both signals closes
// that bypass without needing any new capture hardware or a server-side
// model: a spoofer now has to reproduce two independent motions, one of
// which a flat image cannot produce at all.
import type { FaceLandmarks68 } from "face-api.js";

type Point = { x: number; y: number };
type Landmarks68 = FaceLandmarks68;

const EAR_BLINK_RATIO   = 0.78; // EAR must dip below 78% of the observed "open" baseline to count as closing
const EAR_RECOVER_RATIO = 0.92; // ...then rise back above 92% of that baseline to count as re-opening
const HEAD_TURN_RATIO   = 0.12; // nose-vs-eye-center lateral shift, normalized by inter-eye width
const BASELINE_SAMPLES  = 5;    // frames averaged before the "eyes open" / "centered" baseline is trusted
const EAR_HISTORY_SIZE  = 40;   // rolling window the "eyes open" baseline is read from
const EAR_BASELINE_PCT  = 0.9;  // baseline = 90th percentile of that window, not its single maximum

/** Value at fraction `p` (0-1) of the sorted samples — nearest-rank, no interpolation. */
function percentile(samples: number[], p: number): number {
  if (samples.length === 0) return 0;
  const sorted = [...samples].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
}

function median(samples: number[]): number {
  return percentile(samples, 0.5);
}

function distance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/** Eye Aspect Ratio for one eye's 6 landmark points, in dlib's fixed order. */
function eyeAspectRatio(eye: Point[]): number {
  const vertical1   = distance(eye[1], eye[5]);
  const vertical2   = distance(eye[2], eye[4]);
  const horizontal  = distance(eye[0], eye[3]);
  return horizontal === 0 ? 0 : (vertical1 + vertical2) / (2 * horizontal);
}

export interface LivenessResult {
  passed: boolean;
  score:  number; // 0–1, informational only — the backend stores it but never gates on it
  signal: "blink_and_head_turn" | "blink" | "head_turn" | null;
}

/**
 * Call `addSample` once per detected video frame, then `getResult()` at any
 * point to read the current pass/fail state. Plain mutable class (not a
 * reducer) on purpose — it's driven from a requestAnimationFrame loop where
 * triggering a React re-render per frame would be wasteful.
 */
export class LivenessTracker {
  private earBaseline = 0;
  private earSamples: number[] = [];
  private earHistory: number[] = [];
  private eyeClosed = false;
  private blinkDetected = false;
  private minEarDuringBlink = 1;

  private noseBaselineX: number | null = null;
  private noseBaselineSamples: number[] = [];
  private maxHeadTurnRatio = 0;
  private headTurnDetected = false;

  addSample(landmarks: Landmarks68): void {
    this.trackBlink(landmarks);
    this.trackHeadTurn(landmarks);
  }

  private trackBlink(landmarks: Landmarks68): void {
    const ear = (eyeAspectRatio(landmarks.getLeftEye()) + eyeAspectRatio(landmarks.getRightEye())) / 2;

    this.earHistory.push(ear);
    if (this.earHistory.length > EAR_HISTORY_SIZE) this.earHistory.shift();

    if (this.earSamples.length < BASELINE_SAMPLES) {
      this.earSamples.push(ear);
      this.earBaseline = percentile(this.earHistory, EAR_BASELINE_PCT);
      return;
    }
    // "Eyes open" baseline = 90th percentile of the recent window rather than
    // its single maximum. A running max let one noisy/over-wide frame inflate
    // the baseline permanently, after which ordinary open-eye frames read as
    // "closed" — a FALSE blink that a jittery static image could trigger, and
    // a blink threshold that moved around for real users. A percentile keeps
    // the baseline at a genuinely open-eye level (still near the maximum, so
    // a real blink — EAR falling to roughly a third of open — is just as
    // detectable) while ignoring isolated spikes.
    this.earBaseline = percentile(this.earHistory, EAR_BASELINE_PCT);
    if (this.earBaseline === 0) return;

    const ratio = ear / this.earBaseline;
    if (!this.eyeClosed && ratio < EAR_BLINK_RATIO) {
      this.eyeClosed = true;
      this.minEarDuringBlink = ear;
    } else if (this.eyeClosed) {
      this.minEarDuringBlink = Math.min(this.minEarDuringBlink, ear);
      if (ratio > EAR_RECOVER_RATIO) {
        this.eyeClosed = false;
        this.blinkDetected = true;
      }
    }
  }

  private trackHeadTurn(landmarks: Landmarks68): void {
    const leftEye  = landmarks.getLeftEye();
    const rightEye = landmarks.getRightEye();
    const nose     = landmarks.getNose();
    const noseTip  = nose[3]; // dlib point 30 — tip of the nose bridge, stable across expressions

    const eyeXs = [...leftEye, ...rightEye].map(p => p.x);
    const interEyeWidth = Math.max(...eyeXs) - Math.min(...eyeXs);
    if (interEyeWidth === 0) return;

    if (this.noseBaselineX === null) {
      // Median of the first few frames, not frame 1 alone — a single frame
      // caught mid-motion would otherwise mis-centre every later comparison.
      this.noseBaselineSamples.push(noseTip.x);
      if (this.noseBaselineSamples.length >= BASELINE_SAMPLES) {
        this.noseBaselineX = median(this.noseBaselineSamples);
      }
      return;
    }

    const ratio = (noseTip.x - this.noseBaselineX) / interEyeWidth;
    this.maxHeadTurnRatio = Math.max(this.maxHeadTurnRatio, Math.abs(ratio));
    if (this.maxHeadTurnRatio > HEAD_TURN_RATIO) {
      this.headTurnDetected = true;
    }
  }

  /** Which of the two required signals have been observed so far — for live
   *  on-screen guidance only; passing still requires getResult().passed. */
  getProgress(): { blink: boolean; turn: boolean } {
    return { blink: this.blinkDetected, turn: this.headTurnDetected };
  }

  getResult(): LivenessResult {
    const blinkScore    = this.blinkDetected ? Math.min(1, 1 - this.minEarDuringBlink / (this.earBaseline || 1)) / (1 - EAR_BLINK_RATIO) : 0;
    const headTurnScore = Math.min(1, this.maxHeadTurnRatio / HEAD_TURN_RATIO);

    // Both signals required — see this file's module docstring (FR-E-18) for
    // why "either one" was defeatable by a tilted static photo.
    if (this.blinkDetected && this.headTurnDetected) {
      return { passed: true, score: clamp01((blinkScore + headTurnScore) / 2), signal: "blink_and_head_turn" };
    }
    const partialSignal = this.blinkDetected ? "blink" : this.headTurnDetected ? "head_turn" : null;
    return { passed: false, score: clamp01(Math.max(blinkScore, headTurnScore) * 0.5), signal: partialSignal };
  }

  reset(): void {
    this.earBaseline = 0;
    this.earSamples = [];
    this.earHistory = [];
    this.eyeClosed = false;
    this.blinkDetected = false;
    this.minEarDuringBlink = 1;
    this.noseBaselineX = null;
    this.noseBaselineSamples = [];
    this.maxHeadTurnRatio = 0;
    this.headTurnDetected = false;
  }
}

function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(1, n));
}
