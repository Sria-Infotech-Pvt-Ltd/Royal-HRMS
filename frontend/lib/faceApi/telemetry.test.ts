import { describe, expect, it } from "vitest";
import { CaptureTelemetry } from "./telemetry";

describe("CaptureTelemetry", () => {
  it("builds a bounded numbers-only payload", () => {
    const t = new CaptureTelemetry("verify", true);
    t.begin("session-1", "webgl", 1_000);
    t.recordLivenessAttempt();
    t.recordLivenessAttempt();
    t.recordFailure("too_dark");
    t.recordFailure("too_dark");
    t.recordFailure("no_face");
    t.recordAutoResume();
    t.recordManualRetry();
    t.recordLivenessTimeout(true, false);
    t.recordHint("backlit");
    t.recordFps(10);
    t.recordFps(20);

    const p = t.buildPayload("captured", 9_500);
    expect(p).toMatchObject({
      capture_session_id: "session-1", purpose: "verify", outcome: "captured",
      duration_ms: 8_500, liveness_attempts: 2, quality_failures: 3,
      auto_resumes: 1, manual_retries: 1, tf_backend: "webgl", avg_fps: 15,
    });
    expect(p.details).toMatchObject({
      flow_v2: true, failure_reasons: { too_dark: 2, no_face: 1 }, hints_shown: { backlit: 1 },
      liveness_timeouts: 1, blink_seen: 1, turn_seen: 0,
    });
  });

  it("reports null fps when none was sampled and ignores bad samples", () => {
    const t = new CaptureTelemetry("register", false);
    t.begin("s", "cpu", 0);
    t.recordFps(NaN);
    t.recordFps(-3);
    expect(t.buildPayload("cancelled", 10).avg_fps).toBeNull();
  });

  it("begin() resets everything from a previous session", () => {
    const t = new CaptureTelemetry("verify", true);
    t.begin("a", "webgl", 0);
    t.recordFailure("too_far");
    t.begin("b", "cpu", 100);
    const p = t.buildPayload("failed", 200);
    expect(p.quality_failures).toBe(0);
    expect(p.details.failure_reasons).toEqual({});
    expect(p.tf_backend).toBe("cpu");
  });

  it("finish() does nothing before begin() and sends at most once", () => {
    const t = new CaptureTelemetry("verify", true);
    t.finish("cancelled");
    expect(t.isFinished).toBe(false);
  });
});
