import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));

import { CaptureTelemetry } from "./telemetry";
import { API } from "@/lib/api/endpoints";

const T0 = 1_000_000;

function startedSession(purpose: "verify" | "register" = "verify", flowV2 = true) {
  const t = new CaptureTelemetry(purpose, flowV2);
  t.begin("session-abc", "webgl", T0);
  return t;
}

beforeEach(() => { post.mockReset(); post.mockResolvedValue({}); });

describe("buildPayload", () => {
  it("summarises a session as numbers and short codes only", () => {
    const t = startedSession();
    t.recordLivenessAttempt();
    t.recordLivenessAttempt();
    t.recordFailure("too_dark");
    t.recordFailure("too_dark");
    t.recordFailure("not_frontal");
    t.recordManualRetry();
    t.recordHint("too_far");
    t.recordLivenessTimeout(false, true);
    t.recordFps(10);
    t.recordFps(20);
    const p = t.buildPayload("captured", T0 + 8200);

    expect(p).toMatchObject({
      capture_session_id: "session-abc", purpose: "verify", outcome: "captured", duration_ms: 8200,
      liveness_attempts: 2, quality_failures: 3, auto_resumes: 0, manual_retries: 1, tf_backend: "webgl", avg_fps: 15,
    });
    expect(p.details).toMatchObject({
      flow_v2: true, failure_reasons: { too_dark: 2, not_frontal: 1 }, hints_shown: { too_far: 1 },
      liveness_timeouts: 1, blink_seen: 0, turn_seen: 1,
    });
  });

  it("never carries images or descriptors", () => {
    const keys = Object.keys(startedSession().buildPayload("captured", T0));
    expect(keys.sort()).toEqual([
      "auto_resumes", "avg_fps", "capture_session_id", "details", "duration_ms", "liveness_attempts",
      "manual_retries", "outcome", "purpose", "quality_failures", "tf_backend",
    ]);
  });

  it("stays inside the server's bounds", () => {
    const t = new CaptureTelemetry("register", false);
    t.begin("x".repeat(100), "a-very-long-backend-name", T0);
    for (let i = 0; i < 300; i++) t.recordLivenessAttempt();
    for (let i = 0; i < 700; i++) t.recordFailure("f");
    for (let i = 0; i < 80; i++) t.recordManualRetry();
    const p = t.buildPayload("failed", T0 + 10_000_000);
    expect(p.capture_session_id).toHaveLength(64);
    expect(p.tf_backend.length).toBeLessThanOrEqual(16);
    expect(p.duration_ms).toBe(3_600_000);
    expect(p.liveness_attempts).toBe(200);
    expect(p.quality_failures).toBe(500);
    expect(p.manual_retries).toBe(50);
    expect(p.purpose).toBe("register");
    expect(p.details.flow_v2).toBe(false);
  });

  it("reports no fps when none was sampled, and ignores nonsense samples", () => {
    const t = startedSession();
    t.recordFps(0); t.recordFps(-5); t.recordFps(Number.NaN);
    expect(t.buildPayload("cancelled", T0 + 1).avg_fps).toBeNull();
  });
});

describe("finish", () => {
  it("sends exactly once per session, however often it is called", async () => {
    const t = startedSession();
    t.finish("captured");
    t.finish("cancelled");
    t.finish("error");
    await vi.waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenCalledWith(API.attendance.faceCaptureTelemetry, expect.objectContaining({ outcome: "captured" }));
    expect(t.isFinished).toBe(true);
  });

  it("does nothing for a session that never began", () => {
    new CaptureTelemetry("verify", true).finish("cancelled");
    expect(post).not.toHaveBeenCalled();
  });

  it("is fire-and-forget: it returns immediately and never waits for the network", () => {
    post.mockReturnValue(new Promise(() => undefined)); // a request that never settles
    const t = startedSession();
    expect(t.finish("captured")).toBeUndefined();
  });

  it("swallows a failed send instead of surfacing it", async () => {
    post.mockRejectedValue(new Error("network down"));
    const t = startedSession();
    expect(() => t.finish("captured")).not.toThrow();
    await vi.waitFor(() => expect(post).toHaveBeenCalledTimes(1));
  });

  it("a new begin() starts a fresh session that can be sent again", async () => {
    const t = startedSession();
    t.finish("captured");
    t.begin("session-2", "cpu", T0 + 5000);
    expect(t.isFinished).toBe(false);
    t.finish("failed");
    await vi.waitFor(() => expect(post).toHaveBeenCalledTimes(2));
  });
});
