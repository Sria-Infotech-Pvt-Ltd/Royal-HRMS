// Per-camera-session diagnostics for face capture. Numbers and short codes
// only — never frames, images or descriptors. Exists because the retries
// employees complain about happen entirely in the browser (liveness timeouts,
// quality-gate rejections), where the backend's FaceVerificationAttempt table
// can't see them. Sent fire-and-forget: a failure here must never affect a
// clock-in. The summary is read by `manage.py face_clockin_report`.
import { API } from "@/lib/api/endpoints";

export type CapturePurpose = "verify" | "register";
export type CaptureOutcome = "captured" | "cancelled" | "failed" | "error";

export interface CaptureTelemetryPayload {
  capture_session_id: string;
  purpose: CapturePurpose;
  outcome: CaptureOutcome;
  duration_ms: number;
  liveness_attempts: number;
  quality_failures: number;
  auto_resumes: number;
  manual_retries: number;
  tf_backend: string;
  avg_fps: number | null;
  details: Record<string, unknown>;
}

const MAX_FPS_SAMPLES = 60;

export class CaptureTelemetry {
  private sessionId = "";
  private startedAt = 0;
  private finished = false;
  private livenessAttempts = 0;
  private qualityFailures = 0;
  private autoResumes = 0;
  private manualRetries = 0;
  private tfBackend = "";
  private fpsSamples: number[] = [];
  private failureReasons: Record<string, number> = {};
  private hintsShown: Record<string, number> = {};
  private livenessTimeouts = 0;
  private blinkSeen = 0;
  private turnSeen = 0;
  private flags: Record<string, unknown> = {};

  constructor(private readonly purpose: CapturePurpose, private readonly flowV2: boolean) {}

  begin(sessionId: string, tfBackend: string, now: number = Date.now()): void {
    this.sessionId = sessionId;
    this.startedAt = now;
    this.tfBackend = tfBackend;
    this.finished = false;
    this.livenessAttempts = 0;
    this.qualityFailures = 0;
    this.autoResumes = 0;
    this.manualRetries = 0;
    this.fpsSamples = [];
    this.failureReasons = {};
    this.hintsShown = {};
    this.livenessTimeouts = 0;
    this.blinkSeen = 0;
    this.turnSeen = 0;
    this.flags = {};
  }

  setTfBackend(backend: string): void { this.tfBackend = backend; }

  get isFinished(): boolean { return this.finished; }
  get hasBegun(): boolean { return this.startedAt > 0; }

  recordLivenessAttempt(): void { this.livenessAttempts += 1; }
  recordLivenessTimeout(blinkSeen: boolean, turnSeen: boolean): void {
    this.livenessTimeouts += 1;
    if (blinkSeen) this.blinkSeen += 1;
    if (turnSeen) this.turnSeen += 1;
  }
  recordAutoResume(): void { this.autoResumes += 1; }
  recordManualRetry(): void { this.manualRetries += 1; }
  recordFlag(key: string, value: unknown): void { this.flags[key] = value; }

  /** One rejected frame/attempt, tagged with a short reason code. */
  recordFailure(code: string): void {
    this.qualityFailures += 1;
    this.failureReasons[code] = (this.failureReasons[code] ?? 0) + 1;
  }

  recordHint(code: string): void { this.hintsShown[code] = (this.hintsShown[code] ?? 0) + 1; }

  recordFps(fps: number): void {
    if (!Number.isFinite(fps) || fps <= 0) return;
    if (this.fpsSamples.length < MAX_FPS_SAMPLES) this.fpsSamples.push(fps);
  }

  buildPayload(outcome: CaptureOutcome, now: number = Date.now()): CaptureTelemetryPayload {
    const avgFps = this.fpsSamples.length
      ? Math.round((this.fpsSamples.reduce((a, b) => a + b, 0) / this.fpsSamples.length) * 10) / 10
      : null;
    return {
      capture_session_id: this.sessionId.slice(0, 64),
      purpose: this.purpose,
      outcome,
      duration_ms: Math.max(0, Math.min(3_600_000, Math.round(now - this.startedAt))),
      liveness_attempts: Math.min(200, this.livenessAttempts),
      quality_failures: Math.min(500, this.qualityFailures),
      auto_resumes: Math.min(50, this.autoResumes),
      manual_retries: Math.min(50, this.manualRetries),
      tf_backend: this.tfBackend.slice(0, 16),
      avg_fps: avgFps,
      details: {
        flow_v2: this.flowV2,
        failure_reasons: this.failureReasons,
        hints_shown: this.hintsShown,
        liveness_timeouts: this.livenessTimeouts,
        blink_seen: this.blinkSeen,
        turn_seen: this.turnSeen,
        ...this.flags,
      },
    };
  }

  /** Idempotent — only the first call per session sends anything. */
  finish(outcome: CaptureOutcome): void {
    if (this.finished || !this.hasBegun) return;
    this.finished = true;
    void sendCaptureTelemetry(this.buildPayload(outcome));
  }
}

export async function sendCaptureTelemetry(payload: CaptureTelemetryPayload): Promise<void> {
  try {
    const { default: clientApi } = await import("@/lib/clientApi");
    await clientApi.post(API.attendance.faceCaptureTelemetry, payload);
  } catch {
    // Diagnostics only — never surface or retry.
  }
}
