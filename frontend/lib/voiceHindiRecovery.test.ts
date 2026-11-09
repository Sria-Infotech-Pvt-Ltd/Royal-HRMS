import { describe, expect, it } from "vitest";
import {
  LOW_CONFIDENCE_THRESHOLD, NO_MATCH_INTENT, shouldAttemptHindiRecovery, shouldDeferForLowConfidence,
} from "./voiceHindiRecovery";

describe("shouldAttemptHindiRecovery", () => {
  it("retries a mic-sourced final no-match", () => {
    expect(shouldAttemptHindiRecovery(true, { success: false, intent: NO_MATCH_INTENT, isClarification: false })).toBe(true);
  });

  it("retries a mic-sourced 'did you mean X?' clarification question (is_clarification)", () => {
    expect(shouldAttemptHindiRecovery(true, { success: true, intent: "check_leave_balance", isClarification: true })).toBe(true);
  });

  it("never retries typed input, whatever the outcome", () => {
    expect(shouldAttemptHindiRecovery(false, { success: false, intent: NO_MATCH_INTENT, isClarification: false })).toBe(false);
    expect(shouldAttemptHindiRecovery(false, { success: true, intent: "x", isClarification: true })).toBe(false);
  });

  it("does not retry an ordinary success, a normal slot-filling question, or a non-no-match failure", () => {
    expect(shouldAttemptHindiRecovery(true, { success: true, intent: "check_leave_balance", isClarification: false })).toBe(false);
    expect(shouldAttemptHindiRecovery(true, { success: true, intent: "apply_leave", isClarification: false })).toBe(false);
    expect(shouldAttemptHindiRecovery(true, { success: false, intent: "clock_in", isClarification: false })).toBe(false);
  });

  it("a successful no_match-named outcome is not treated as a failed no-match", () => {
    expect(shouldAttemptHindiRecovery(true, { success: true, intent: NO_MATCH_INTENT, isClarification: false })).toBe(false);
  });
});

describe("shouldDeferForLowConfidence", () => {
  it("uses the approved initial threshold of 0.5", () => {
    expect(LOW_CONFIDENCE_THRESHOLD).toBe(0.5);
  });

  it("defers strictly below the threshold only", () => {
    expect(shouldDeferForLowConfidence(0.49)).toBe(true);
    expect(shouldDeferForLowConfidence(0)).toBe(true);
    expect(shouldDeferForLowConfidence(0.5)).toBe(false);
    expect(shouldDeferForLowConfidence(0.93)).toBe(false);
  });

  it("treats a missing confidence as no signal, never as low confidence", () => {
    expect(shouldDeferForLowConfidence(undefined)).toBe(false);
  });
});
