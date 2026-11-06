// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { saveLockoutUntil } from "@/lib/faceApi/lockout";

// Integration test: the REAL useVoiceCommand + postVoiceParse + useVoiceLockout + lockout lib + Hindi recovery logic,
// with only the network (clientApi), toasts, TTS fetch and the Sarvam mic capture replaced.
const post = vi.fn();
const showToast = vi.fn();
const fetchSpeechAudio = vi.fn();
const captureAndTranscribeViaSarvam = vi.fn();
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/lib/voiceTts", () => ({ fetchSpeechAudio: (...args: unknown[]) => fetchSpeechAudio(...args) }));
vi.mock("@/lib/voiceSttFallback", () => ({
  captureAndTranscribeViaSarvam: (...args: unknown[]) => captureAndTranscribeViaSarvam(...args),
}));

import { useVoiceCommand } from "./useVoiceCommand";

const LOCKOUT_KEY = "aira_face_lockout_until";

function reply(data: Record<string, unknown>) {
  return {
    data: {
      // postVoiceParse prefers the envelope's own message, so it must follow the per-test message.
      message: (data.message as string | undefined) ?? "Server message.",
      data: {
        intent: "check_leave_balance", confidence: 95, result: null, message: "Server message.", speech_message: null,
        conversational: false, awaiting_input: false, success: true, language: "en", is_clarification: false,
        ...data,
      },
    },
  };
}
const FACE_PROOF_TURN = {
  intent: "clock_in", conversational: true, awaiting_input: true, result: { awaiting_face_proof: true },
  message: "Taking facial proof - please look at the camera.",
};
const BLOCKED = {
  intent: "clock_in", success: false, result: { blocked: true, retry_after_seconds: 120 },
  message: "Too many failed face verification attempts.",
};
const SARVAM_RESULT = { transcript: "mera leave balance", languageProbability: 0.9, wasLanguageHinted: true, detectedLanguage: "hi" };

// Minimal SpeechRecognition stand-in the hook can drive and the test can feed.
type Handlers = {
  onresult?: (event: unknown) => void; onend?: () => void; onerror?: (event: unknown) => void;
};
let recognitions: Array<Handlers & { start: () => void; stop: () => void; abort: () => void }>;
class FakeRecognition {
  continuous = false; interimResults = false; lang = "";
  onresult?: Handlers["onresult"]; onend?: Handlers["onend"]; onerror?: Handlers["onerror"];
  start = vi.fn(); stop = vi.fn(); abort = vi.fn();
  constructor() { recognitions.push(this); }
}
function finalChunk(transcript: string, confidence?: number) {
  const alternative = confidence === undefined ? { transcript } : { transcript, confidence };
  return { resultIndex: 0, results: [Object.assign([alternative], { isFinal: true, length: 1 })] };
}

class FakeAudio {
  static instances: FakeAudio[] = [];
  onended?: () => void; onerror?: () => void; pause = vi.fn(); src: string;
  constructor(src: string) { this.src = src; FakeAudio.instances.push(this); }
  play() { return Promise.resolve(); }
}

function setup(isMuted = false) {
  return renderHook(({ muted }) => useVoiceCommand(muted, true), { initialProps: { muted: isMuted } });
}

beforeEach(() => {
  window.sessionStorage.clear();
  recognitions = [];
  FakeAudio.instances = [];
  post.mockReset(); showToast.mockReset(); fetchSpeechAudio.mockReset(); captureAndTranscribeViaSarvam.mockReset();
  fetchSpeechAudio.mockResolvedValue(null); // TTS unavailable unless a test says otherwise
  captureAndTranscribeViaSarvam.mockResolvedValue(null);
  Object.defineProperty(window, "SpeechRecognition", { value: FakeRecognition, configurable: true, writable: true });
  vi.stubGlobal("Audio", FakeAudio);
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:test"), configurable: true, writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), configurable: true, writable: true });
});
afterEach(() => {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
});

describe("blocked voice responses record the shared lockout", () => {
  it("submitTranscript: a blocked punch stores the lockout and shows its countdown", async () => {
    post.mockResolvedValue(reply(BLOCKED));
    const { result } = setup();
    await act(async () => { await result.current.submitTranscript("punch in", false); });
    expect(window.sessionStorage.getItem(LOCKOUT_KEY)).not.toBeNull();
    expect(result.current.lockoutSecondsRemaining).toBeGreaterThanOrEqual(119);
    expect(result.current.lockoutSecondsRemaining).toBeLessThanOrEqual(120);
    // The server's own message is still what the panel shows for the blocked answer.
    expect(result.current.conversation?.message).toBe("Too many failed face verification attempts.");
    expect(result.current.conversation?.resultStatus).toBe("error");
  });

  it("submitFaceProof: a blocked answer to a captured face records the lockout and closes the camera turn", async () => {
    post.mockResolvedValueOnce(reply(FACE_PROOF_TURN));
    const { result } = setup();
    await act(async () => { await result.current.submitTranscript("punch in", false); });
    expect(result.current.conversation?.awaitingFaceProof).toBe(true);

    post.mockResolvedValueOnce(reply(BLOCKED));
    await act(async () => { await result.current.submitFaceProof([0.1], 0.9, "session-1"); });
    expect(window.sessionStorage.getItem(LOCKOUT_KEY)).not.toBeNull();
    expect(result.current.lockoutSecondsRemaining).toBeGreaterThan(0);
    expect(result.current.conversation?.awaitingFaceProof).toBe(false);
    expect(result.current.conversation?.awaitingInput).toBe(false);
  });
});

describe("an active local lockout keeps the camera shut (Decision A)", () => {
  it("a face-proof turn during a lockout never sets awaitingFaceProof and shows the countdown notice", async () => {
    saveLockoutUntil(Date.now() + 90_000);
    post.mockResolvedValue(reply(FACE_PROOF_TURN));
    const { result } = setup();
    await act(async () => { await result.current.submitTranscript("punch in", false); });
    expect(result.current.conversation?.awaitingFaceProof).toBe(false);
    expect(result.current.conversation?.awaitingInput).toBe(false);
    expect(result.current.conversation?.resultStatus).toBe("error");
    expect(result.current.conversation?.message).toMatch(/^Face check locked\. Try again in 01:(29|30)$/);
  });

  it("the microphone stays usable for unrelated commands while locked", async () => {
    saveLockoutUntil(Date.now() + 90_000);
    post.mockResolvedValue(reply({ message: "You have 3 days.", intent: "check_leave_balance" }));
    const { result } = setup();
    await act(async () => { await result.current.submitTranscript("check my leave balance", false); });
    expect(result.current.conversation?.message).toBe("You have 3 days.");
    expect(result.current.conversation?.resultStatus).toBe("success");
    act(() => result.current.startListening());
    expect(recognitions).toHaveLength(1);
    expect(recognitions[0].start).toHaveBeenCalled();
    expect(result.current.isDisabled).toBe(false);
  });

  it("the normal face-proof flow resumes once the lockout has expired", async () => {
    saveLockoutUntil(Date.now() - 1000); // already over
    post.mockResolvedValue(reply(FACE_PROOF_TURN));
    const { result } = setup();
    await act(async () => { await result.current.submitTranscript("punch in", false); });
    expect(result.current.conversation?.awaitingFaceProof).toBe(true);
    expect(result.current.conversation?.message).toBe("Taking facial proof - please look at the camera.");
    expect(result.current.lockoutSecondsRemaining).toBe(0);
  });
});

describe("Hindi recovery is triggered by is_clarification and never loops", () => {
  it("a mic-sourced clarification question is retried once through Sarvam and the retry result is used", async () => {
    captureAndTranscribeViaSarvam.mockResolvedValue(SARVAM_RESULT);
    post
      .mockResolvedValueOnce(reply({ is_clarification: true, awaiting_input: true, conversational: true, message: "Did you mean X?" }))
      .mockResolvedValueOnce(reply({ message: "You have 3 days." }));
    const { result } = setup();
    await act(async () => { await result.current.submitTranscript("leev balans", true); });
    expect(captureAndTranscribeViaSarvam).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledTimes(2);
    expect(post.mock.calls[1][1]).toMatchObject({ transcript: "mera leave balance", stt_detected_language: "hi" });
    expect(result.current.conversation?.message).toBe("You have 3 days.");
    expect(result.current.conversation?.transcript).toBe("mera leave balance");
  });

  it("makes at most one attempt even if the retried parse is a clarification again", async () => {
    captureAndTranscribeViaSarvam.mockResolvedValue(SARVAM_RESULT);
    post.mockResolvedValue(reply({ is_clarification: true, awaiting_input: true, conversational: true, message: "Did you mean X?" }));
    const { result } = setup();
    await act(async () => { await result.current.submitTranscript("leev balans", true); });
    expect(captureAndTranscribeViaSarvam).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledTimes(2);
  });

  it("typed input is never retried, even for a clarification question", async () => {
    post.mockResolvedValue(reply({ is_clarification: true, awaiting_input: true, conversational: true, message: "Did you mean X?" }));
    const { result } = setup();
    await act(async () => { await result.current.submitTranscript("leev balans", false); });
    expect(captureAndTranscribeViaSarvam).not.toHaveBeenCalled();
    expect(post).toHaveBeenCalledTimes(1);
    expect(result.current.conversation?.message).toBe("Did you mean X?");
  });

  it("a normal slot-filling question (is_clarification false) is not retried", async () => {
    post.mockResolvedValue(reply({ awaiting_input: true, conversational: true, message: "Which leave type?" }));
    const { result } = setup();
    await act(async () => { await result.current.submitTranscript("apply leave", true); });
    expect(captureAndTranscribeViaSarvam).not.toHaveBeenCalled();
  });

  it("a final no-match from the mic is still retried once (existing behavior preserved)", async () => {
    captureAndTranscribeViaSarvam.mockResolvedValue(SARVAM_RESULT);
    post
      .mockResolvedValueOnce(reply({ intent: "no_match", success: false, message: "Not related to Aira." }))
      .mockResolvedValueOnce(reply({ message: "You have 3 days." }));
    const { result } = setup();
    await act(async () => { await result.current.submitTranscript("gibberish", true); });
    expect(captureAndTranscribeViaSarvam).toHaveBeenCalledTimes(1);
    expect(result.current.conversation?.message).toBe("You have 3 days.");
  });
});

describe("low browser confidence is recovered BEFORE the first parse", () => {
  async function speak(result: ReturnType<typeof setup>["result"], transcript: string, confidence?: number) {
    act(() => result.current.startListening());
    await waitFor(() => expect(recognitions).toHaveLength(1));
    act(() => recognitions[0].onresult?.(finalChunk(transcript, confidence)));
    await act(async () => { recognitions[0].onend?.(); });
  }

  it("asks Sarvam first, then parses the Sarvam transcript (no parse happened before)", async () => {
    captureAndTranscribeViaSarvam.mockResolvedValue(SARVAM_RESULT);
    post.mockResolvedValue(reply({ message: "You have 3 days." }));
    const { result } = setup();
    await speak(result, "punch in", 0.3);
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(captureAndTranscribeViaSarvam).toHaveBeenCalledTimes(1);
    expect(captureAndTranscribeViaSarvam.mock.invocationCallOrder[0]).toBeLessThan(post.mock.invocationCallOrder[0]);
    expect(post.mock.calls[0][1]).toMatchObject({ transcript: "mera leave balance" });
  });

  it("falls back to the ORIGINAL transcript when Sarvam returns nothing, with no second Sarvam attempt", async () => {
    captureAndTranscribeViaSarvam.mockResolvedValue(null);
    post.mockResolvedValue(reply({ intent: "no_match", success: false, message: "Not related to Aira." }));
    const { result } = setup();
    await speak(result, "punch in", 0.2);
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post.mock.calls[0][1]).toMatchObject({ transcript: "punch in" });
    expect(captureAndTranscribeViaSarvam).toHaveBeenCalledTimes(1);
  });

  it("does not defer at or above the 0.5 threshold, or when the browser gives no confidence", async () => {
    post.mockResolvedValue(reply({ message: "You have 3 days." }));
    const { result } = setup();
    await speak(result, "check my leave balance", 0.5);
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(captureAndTranscribeViaSarvam).not.toHaveBeenCalled();

    recognitions = [];
    await speak(result, "check my leave balance", undefined);
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
    expect(captureAndTranscribeViaSarvam).not.toHaveBeenCalled();
  });

  it("uses the LOWEST final-chunk confidence of the session", async () => {
    captureAndTranscribeViaSarvam.mockResolvedValue(SARVAM_RESULT);
    post.mockResolvedValue(reply({ message: "You have 3 days." }));
    const { result } = setup();
    act(() => result.current.startListening());
    await waitFor(() => expect(recognitions).toHaveLength(1));
    act(() => recognitions[0].onresult?.(finalChunk("check my", 0.9)));
    act(() => recognitions[0].onresult?.(finalChunk(" leave balance", 0.4)));
    await act(async () => { recognitions[0].onend?.(); });
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(captureAndTranscribeViaSarvam).toHaveBeenCalledTimes(1);
  });
});

describe("TTS failure and muting", () => {
  it("tells the user when a spoken reply is unavailable", async () => {
    post.mockResolvedValue(reply({ message: "You have 3 days." }));
    const { result } = setup(false);
    await act(async () => { await result.current.submitTranscript("check my leave balance", false); });
    await waitFor(() => expect(showToast).toHaveBeenCalledWith("Voice response unavailable, showing text only", "error"));
  });

  it("says nothing about TTS when muted (nothing was attempted)", async () => {
    post.mockResolvedValue(reply({ message: "You have 3 days." }));
    const { result } = setup(true);
    await act(async () => { await result.current.submitTranscript("check my leave balance", false); });
    expect(fetchSpeechAudio).not.toHaveBeenCalled();
    expect(showToast).not.toHaveBeenCalledWith("Voice response unavailable, showing text only", "error");
  });

  it("muting while a reply is playing stops that audio at once", async () => {
    fetchSpeechAudio.mockResolvedValue(new Blob(["x"], { type: "audio/wav" }));
    post.mockResolvedValue(reply({ message: "You have 3 days." }));
    const { result, rerender } = setup(false);
    await act(async () => { await result.current.submitTranscript("check my leave balance", false); });
    await waitFor(() => expect(FakeAudio.instances).toHaveLength(1));
    expect(FakeAudio.instances[0].pause).not.toHaveBeenCalled();
    rerender({ muted: true });
    expect(FakeAudio.instances[0].pause).toHaveBeenCalled();
  });

  it("un-muting does not interrupt anything", async () => {
    fetchSpeechAudio.mockResolvedValue(new Blob(["x"], { type: "audio/wav" }));
    post.mockResolvedValue(reply({ message: "You have 3 days." }));
    const { result, rerender } = setup(true);
    rerender({ muted: false });
    await act(async () => { await result.current.submitTranscript("check my leave balance", false); });
    await waitFor(() => expect(FakeAudio.instances).toHaveLength(1));
    expect(FakeAudio.instances[0].pause).not.toHaveBeenCalled();
  });
});
