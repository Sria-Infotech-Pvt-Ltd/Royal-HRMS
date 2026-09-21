import { describe, expect, it } from "vitest";
import {
  shouldAttemptHindiRecovery,
  shouldDeferForLowConfidence,
  NO_MATCH_INTENT,
} from "@/lib/voiceHindiRecovery";

describe("shouldAttemptHindiRecovery", () => {
  it("is false for a typed answer, regardless of outcome", () => {
    expect(
      shouldAttemptHindiRecovery(false, { success: false, intent: NO_MATCH_INTENT, isClarification: false }),
    ).toBe(false);
    expect(
      shouldAttemptHindiRecovery(false, { success: true, intent: "cancel_leave", isClarification: true }),
    ).toBe(false);
  });

  it("is true for a mic transcript that hard-failed to match anything", () => {
    expect(
      shouldAttemptHindiRecovery(true, { success: false, intent: NO_MATCH_INTENT, isClarification: false }),
    ).toBe(true);
  });

  it("is false for a mic transcript that failed for a reason OTHER than no-match", () => {
    expect(
      shouldAttemptHindiRecovery(true, { success: false, intent: "clock_in", isClarification: false }),
    ).toBe(false);
  });

  it("is true for a mic transcript that matched but only reached a clarification question", () => {
    expect(
      shouldAttemptHindiRecovery(true, { success: true, intent: "cancel_leave", isClarification: true }),
    ).toBe(true);
  });

  it("is false for a mic transcript that matched and executed real logic", () => {
    expect(
      shouldAttemptHindiRecovery(true, { success: true, intent: "cancel_leave", isClarification: false }),
    ).toBe(false);
  });
});

describe("shouldDeferForLowConfidence", () => {
  it("is false when no confidence signal is available", () => {
    expect(shouldDeferForLowConfidence(undefined)).toBe(false);
  });

  it("is true below the threshold", () => {
    expect(shouldDeferForLowConfidence(0.2)).toBe(true);
    expect(shouldDeferForLowConfidence(0.49)).toBe(true);
  });

  it("is false at or above the threshold", () => {
    expect(shouldDeferForLowConfidence(0.5)).toBe(false);
    expect(shouldDeferForLowConfidence(0.9)).toBe(false);
  });

  it("treats an explicit 0 as a real (low) signal, not as missing", () => {
    expect(shouldDeferForLowConfidence(0)).toBe(true);
  });
});
