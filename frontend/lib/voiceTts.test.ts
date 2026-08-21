import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mocked before importing the module under test — vi.mock is hoisted above
// imports by Vitest, so this ordering is safe despite appearing "after" the
// import below in source order.
vi.mock("@/lib/clientApi", () => ({
  default: { post: vi.fn() },
}));

import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { fetchSpeechAudio, toSarvamLanguageCode } from "@/lib/voiceTts";

const mockPost = clientApi.post as unknown as ReturnType<typeof vi.fn>;

describe("toSarvamLanguageCode", () => {
  it("maps hi to hi-IN", () => {
    expect(toSarvamLanguageCode("hi")).toBe("hi-IN");
  });

  it("maps en to en-IN", () => {
    expect(toSarvamLanguageCode("en")).toBe("en-IN");
  });
});

describe("fetchSpeechAudio", () => {
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockPost.mockReset();
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  it("sends the correct text and language_code, with blob responseType, and returns a Blob on success", async () => {
    const fakeBytes = new Uint8Array([1, 2, 3]);
    mockPost.mockResolvedValue({ data: fakeBytes });

    const result = await fetchSpeechAudio("Hello there", "en");

    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, body, config] = mockPost.mock.calls[0];
    expect(url).toBe(API.voice.speak);
    expect(body).toEqual({ text: "Hello there", language_code: "en-IN" });
    expect(config).toMatchObject({ responseType: "blob" });
    expect(result).toBeInstanceOf(Blob);
    expect(result?.type).toBe("audio/wav");
  });

  it("sends hi-IN for a Hindi response", async () => {
    mockPost.mockResolvedValue({ data: new Uint8Array([1]) });

    await fetchSpeechAudio("नमस्ते", "hi");

    const [, body] = mockPost.mock.calls[0];
    expect(body).toEqual({ text: "नमस्ते", language_code: "hi-IN" });
  });

  it.each([
    [422, "request rejected (invalid text/language)"],
    [429, "rate-limited"],
    [503, "service unavailable"],
    [504, "request timed out upstream"],
    [502, "upstream error"],
  ])("returns null and logs distinctly for a %s response, without retrying", async (status, expectedFragment) => {
    mockPost.mockRejectedValue({ status, message: `boom-${status}` });

    const result = await fetchSpeechAudio("Hello", "en");

    expect(result).toBeNull();
    // Each of these statuses is a real response FROM the backend — Phase 5's
    // sarvam_client.py already retried (or immediately rejected, for 422)
    // before returning it, so fetchSpeechAudio must never re-send the
    // request itself: doing so would compound backend-side retries with an
    // independent frontend retry loop, exactly the "retry storm" the phase
    // was scoped to avoid.
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(errorSpy).toHaveBeenCalledTimes(1);
    const logged = errorSpy.mock.calls[0][0] as string;
    expect(logged).toContain(expectedFragment);
    expect(logged).toContain(`boom-${status}`);
  });

  it("returns null and logs a generic failure for a plain network error with no status", async () => {
    mockPost.mockRejectedValue({ message: "Network Error" });

    const result = await fetchSpeechAudio("Hello", "en");

    expect(result).toBeNull();
    expect(errorSpy).toHaveBeenCalledTimes(1);
    const logged = errorSpy.mock.calls[0][0] as string;
    expect(logged).toContain("failed");
    expect(logged).toContain("Network Error");
  });

  describe("retry on a true network failure (status 500 — never reached the backend)", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("retries once and returns the blob when the retry succeeds", async () => {
      mockPost
        .mockRejectedValueOnce({ status: 500, message: "Network Error" })
        .mockResolvedValueOnce({ data: new Uint8Array([9]) });

      const promise = fetchSpeechAudio("Hello", "en");
      await vi.advanceTimersByTimeAsync(500);
      const result = await promise;

      expect(mockPost).toHaveBeenCalledTimes(2);
      expect(result).toBeInstanceOf(Blob);
      // First failure logs that a retry is coming.
      expect(errorSpy).toHaveBeenCalledTimes(1);
      expect(errorSpy.mock.calls[0][0] as string).toContain("retrying (attempt 2/2)");
    });

    it("gives up and returns null once the single retry also fails", async () => {
      mockPost.mockRejectedValue({ status: 500, message: "Network Error" });

      const promise = fetchSpeechAudio("Hello", "en");
      await vi.advanceTimersByTimeAsync(500);
      const result = await promise;

      expect(mockPost).toHaveBeenCalledTimes(2);
      expect(result).toBeNull();
      expect(errorSpy).toHaveBeenCalledTimes(2);
      expect(errorSpy.mock.calls[0][0] as string).toContain("retrying (attempt 2/2)");
      expect(errorSpy.mock.calls[1][0] as string).toContain("giving up after 2 attempts");
    });

    it("does not retry a backend-mapped status even if it happens to repeat", async () => {
      // Sanity check that the retry gate is genuinely status-based, not
      // just "did the first call fail" — a 429 must never retry even
      // though it's a rejected promise same as the 500 case above.
      mockPost.mockRejectedValue({ status: 429, message: "rate limited" });

      const result = await fetchSpeechAudio("Hello", "en");

      expect(mockPost).toHaveBeenCalledTimes(1);
      expect(result).toBeNull();
    });
  });

  it("distinguishes each status with its own, different log message", async () => {
    const statuses = [422, 429, 503, 504, 502];
    const messages: string[] = [];
    for (const status of statuses) {
      mockPost.mockRejectedValueOnce({ status, message: "x" });
      await fetchSpeechAudio("Hello", "en");
      messages.push(errorSpy.mock.calls[errorSpy.mock.calls.length - 1][0] as string);
    }
    expect(new Set(messages).size).toBe(statuses.length);
  });
});
