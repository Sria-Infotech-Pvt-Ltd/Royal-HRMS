// Liveness detection: proves the camera is looking at a live person, not a
// static photo held up to it, by tracking real movement across frames —
// either a natural blink or a slight head turn. A single still frame can
// never pass this; it requires landmark positions to actually change over
// a short window of time.
//
// Two independent signals are tracked; either one passing is enough:
//   1. Blink  — Eye Aspect Ratio (Soukupová & Čech) dipping and recovering.
//   2. Head turn — the nose tip shifting laterally relative to the eyes.
// Both are normalized against the detected face's own size, so thresholds
// don't depend on how close the camera is.
import type { FaceLandmarks68 } from "face-api.js";

type Point = { x: number; y: number };
type Landmarks68 = FaceLandmarks68;

const EAR_BLINK_RATIO   = 0.78; // EAR must dip below 78% of the observed "open" baseline to count as closing
const EAR_RECOVER_RATIO = 0.92; // ...then rise back above 92% of that baseline to count as re-opening
const HEAD_TURN_RATIO   = 0.12; // nose-vs-eye-center lateral shift, normalized by inter-eye width
const BASELINE_SAMPLES  = 5;    // frames averaged before the "eyes open" / "centered" baseline is trusted

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
  signal: "blink" | "head_turn" | null;
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
  private eyeClosed = false;
  private blinkDetected = false;
  private minEarDuringBlink = 1;

  private noseBaselineX: number | null = null;
  private maxHeadTurnRatio = 0;
  private headTurnDetected = false;

  addSample(landmarks: Landmarks68): void {
    this.trackBlink(landmarks);
    this.trackHeadTurn(landmarks);
  }

  private trackBlink(landmarks: Landmarks68): void {
    const ear = (eyeAspectRatio(landmarks.getLeftEye()) + eyeAspectRatio(landmarks.getRightEye())) / 2;

    if (this.earSamples.length < BASELINE_SAMPLES) {
      this.earSamples.push(ear);
      this.earBaseline = Math.max(this.earBaseline, ear);
      return;
    }
    // Keep tracking the running max — a well-lit, eyes-open frame is the
    // best baseline available and can arrive at any point in the window.
    this.earBaseline = Math.max(this.earBaseline, ear);
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
      this.noseBaselineX = noseTip.x;
      return;
    }

    const ratio = (noseTip.x - this.noseBaselineX) / interEyeWidth;
    this.maxHeadTurnRatio = Math.max(this.maxHeadTurnRatio, Math.abs(ratio));
    if (this.maxHeadTurnRatio > HEAD_TURN_RATIO) {
      this.headTurnDetected = true;
    }
  }

  getResult(): LivenessResult {
    const blinkScore    = this.blinkDetected ? Math.min(1, 1 - this.minEarDuringBlink / (this.earBaseline || 1)) / (1 - EAR_BLINK_RATIO) : 0;
    const headTurnScore = Math.min(1, this.maxHeadTurnRatio / HEAD_TURN_RATIO);

    if (this.blinkDetected) return { passed: true, score: clamp01(blinkScore), signal: "blink" };
    if (this.headTurnDetected) return { passed: true, score: clamp01(headTurnScore), signal: "head_turn" };
    return { passed: false, score: clamp01(Math.max(blinkScore, headTurnScore) * 0.5), signal: null };
  }

  reset(): void {
    this.earBaseline = 0;
    this.earSamples = [];
    this.eyeClosed = false;
    this.blinkDetected = false;
    this.minEarDuringBlink = 1;
    this.noseBaselineX = null;
    this.maxHeadTurnRatio = 0;
    this.headTurnDetected = false;
  }
}

function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(1, n));
}
