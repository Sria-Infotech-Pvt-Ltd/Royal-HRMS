import { describe, expect, it } from "vitest";
import { parseTranscribeFallbackResponseData } from "@/lib/voiceSttFallback";

describe("parseTranscribeFallbackResponseData", () => {
  it("returns null when there is no usable transcript", () => {
    expect(parseTranscribeFallbackResponseData(undefined)).toBeNull();
    expect(parseTranscribeFallbackResponseData({ transcript: "" })).toBeNull();
    expect(parseTranscribeFallbackResponseData({ transcript: "   " })).toBeNull();
  });

  it("reports detectedLanguage='hi' when the Hindi (primary) hint tier won", () => {
    const result = parseTranscribeFallbackResponseData({
      transcript: "mujhe leave chahiye",
      was_language_hinted: true,
      detected_language: "hi",
    });

    expect(result).not.toBeNull();
    expect(result?.detectedLanguage).toBe("hi");
    // The pre-existing signal is untouched by the new field's presence —
    // still true whenever the retry succeeded via either hinted tier.
    expect(result?.wasLanguageHinted).toBe(true);
  });

  it("reports detectedLanguage='en' when the English fallback tier won — the exact case wasLanguageHinted alone could not distinguish (Phase 3.1's Gap 2)", () => {
    const result = parseTranscribeFallbackResponseData({
      transcript: "clock me in",
      was_language_hinted: true, // unchanged: still true, same as the Hindi-tier case above
      detected_language: "en",
    });

    expect(result).not.toBeNull();
    expect(result?.detectedLanguage).toBe("en");
    expect(result?.wasLanguageHinted).toBe(true);
  });

  it("falls back to detectedLanguage=null for a missing or unrecognized value", () => {
    expect(parseTranscribeFallbackResponseData({ transcript: "hello" })?.detectedLanguage).toBeNull();
    expect(
      parseTranscribeFallbackResponseData({ transcript: "hello", detected_language: "fr" })?.detectedLanguage,
    ).toBeNull();
  });

  it("still resolves languageProbability independently of detectedLanguage", () => {
    const result = parseTranscribeFallbackResponseData({
      transcript: "hello", language_probability: 0.42, detected_language: "en",
    });
    expect(result?.languageProbability).toBe(0.42);
  });
});
