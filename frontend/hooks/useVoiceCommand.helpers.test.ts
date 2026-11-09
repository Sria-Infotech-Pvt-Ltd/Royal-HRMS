// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { shouldAttemptHindiRecovery } from "@/lib/voiceHindiRecovery";
import type { VoiceParseOutcome } from "./useVoiceCommand.types";

const post = vi.fn();
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));

import { applyFaceLockoutGuard, postVoiceParse } from "./useVoiceCommand.helpers";

function envelope(data: Record<string, unknown>) {
  return {
    data: {
      message: "msg",
      data: {
        intent: "check_leave_balance", confidence: 90, result: null, message: "msg", speech_message: null,
        conversational: false, awaiting_input: false, success: true, language: "en", is_clarification: false,
        ...data,
      },
    },
  };
}

beforeEach(() => post.mockReset());

describe("postVoiceParse response mapping", () => {
  it("maps is_clarification to isClarification", async () => {
    post.mockResolvedValue(envelope({ is_clarification: true, awaiting_input: true }));
    expect((await postVoiceParse("leev balans", "en")).isClarification).toBe(true);
  });

  it("defaults isClarification to false when the field is absent or false", async () => {
    post.mockResolvedValue(envelope({ is_clarification: false }));
    expect((await postVoiceParse("x", "en")).isClarification).toBe(false);
    post.mockResolvedValue({ data: { message: "m", data: { intent: "x" } } });
    expect((await postVoiceParse("x", "en")).isClarification).toBe(false);
  });

  it("preserves a blocked result with its retry_after_seconds rather than dropping it", async () => {
    post.mockResolvedValue(envelope({
      intent: "clock_in", success: false, result: { blocked: true, retry_after_seconds: 120 },
      message: "Too many failed face verification attempts.",
    }));
    const outcome = await postVoiceParse("punch in", "en");
    expect(outcome.success).toBe(false);
    expect(outcome.result).toEqual({ blocked: true, retry_after_seconds: 120 });
  });

  it("keeps the existing fields intact", async () => {
    post.mockResolvedValue(envelope({ language: "hi", conversational: true, awaiting_input: true, speech_message: "s" }));
    const outcome = await postVoiceParse("x", "en");
    expect(outcome).toMatchObject({
      intent: "check_leave_balance", language: "hi", conversational: true, awaitingInput: true, speechMessage: "s",
    });
  });

  it("feeds is_clarification into the Hindi recovery decision", async () => {
    post.mockResolvedValue(envelope({ is_clarification: true, awaiting_input: true }));
    const clarification = await postVoiceParse("x", "en");
    expect(shouldAttemptHindiRecovery(true, clarification)).toBe(true);
    expect(shouldAttemptHindiRecovery(false, clarification)).toBe(false);
    post.mockResolvedValue(envelope({ awaiting_input: true })); // an ordinary slot-filling question
    expect(shouldAttemptHindiRecovery(true, await postVoiceParse("x", "en"))).toBe(false);
  });
});

function outcome(overrides: Partial<VoiceParseOutcome> = {}): VoiceParseOutcome {
  return {
    intent: "clock_in", message: "Taking facial proof - please look at the camera.", speechMessage: "spoken",
    conversational: true, awaitingInput: true, success: true, result: { awaiting_face_proof: true },
    language: "hi", isClarification: false, ...overrides,
  };
}

describe("applyFaceLockoutGuard (Decision A)", () => {
  it("turns a face-proof turn into a terminal 'Face check locked' answer while a lockout is active", () => {
    const guarded = applyFaceLockoutGuard(outcome(), 75);
    expect(guarded.message).toBe("Face check locked. Try again in 01:15");
    expect(guarded.awaitingInput).toBe(false);
    expect(guarded.success).toBe(false);
    expect(guarded.speechMessage).toBeNull();
    expect(guarded.language).toBe("en");
    expect(guarded.result).toEqual({ blocked: true, retry_after_seconds: 75 });
  });

  it("leaves the face-proof turn untouched when there is no lockout", () => {
    const original = outcome();
    expect(applyFaceLockoutGuard(original, 0)).toBe(original);
  });

  it("never alters a response that is not a face-proof turn", () => {
    const answer = outcome({ intent: "check_leave_balance", awaitingInput: false, result: { balance: 3 } });
    expect(applyFaceLockoutGuard(answer, 60)).toBe(answer);
    const question = outcome({ awaitingInput: true, result: { awaiting_slot: "leave_type" } });
    expect(applyFaceLockoutGuard(question, 60)).toBe(question);
  });
});
