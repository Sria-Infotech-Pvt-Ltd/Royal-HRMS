import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

/**
 * POST /api/voice/speak/ (Sarvam Bulbul TTS via backend/apps/voice_commands/
 * views_speak.py) — the network half of Phase 4's TTS playback swap.
 * useVoiceCommand.ts's speak() calls fetchSpeechAudio() for the network
 * call + status handling, then owns turning the returned Blob into an
 * HTMLAudioElement and playing it (DOM wiring stays in the hook; this
 * module has no DOM dependency, which is what makes it unit-testable
 * without jsdom).
 *
 * Backend speaker is always "shubh" server-side (views_speak.py's own
 * TTS_DEFAULT_SPEAKER) — deliberately never sent from here.
 */

export type TtsLanguage = "en" | "hi";

// Sarvam's TTS endpoint expects a BCP-47-ish code (language_code: "hi-IN" /
// "en-IN"), not this app's bare "en"/"hi" — same convention backend
// views_transcribe.py's own _PRIMARY_LANGUAGE_HINT/_SECONDARY_LANGUAGE_HINT
// already use for the STT side of this same pipeline.
export function toSarvamLanguageCode(language: TtsLanguage): string {
  return language === "hi" ? "hi-IN" : "en-IN";
}

// Sized with margin above views_speak.py's own sarvam_client._TTS_TIMEOUT_SECONDS
// (15s) — same reasoning postVoiceParse's 25000ms and voiceSttFallback.ts's
// 25000ms overrides give for their own backend budgets, scaled down to TTS's
// shorter 15s budget rather than reused verbatim.
const SPEAK_TIMEOUT_MS = 20000;

// Phase 5: fetchSpeechAudio retries exactly once, and ONLY for a failure
// that never got a real response from OUR OWN backend — see
// NETWORK_FAILURE_STATUS's comment. Every failure that DID come back from
// the backend (422/429/502/503/504) reflects a request sarvam_client.py's
// own retry-with-backoff (backend/apps/voice_commands/sarvam_client.py,
// Phase 5) already ran to completion, or an immediate non-transient
// rejection like 422 — retrying those again here would just resend the same
// already-exhausted (or already-hopeless) upstream chain, exactly the
// "compounding retry storm" this phase was told to avoid. So this is a
// SEPARATE, narrower retry than the backend's: it only ever adds one extra
// attempt, and only for the one failure class the backend never had a
// chance to retry (because its own logic never ran at all).
const MAX_ATTEMPTS = 2;
const RETRY_DELAY_MS = 500;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// clientApi's own normaliseError (lib/clientApi.ts) falls back to status 500
// whenever axios never got a real e.response at all — a client-side
// timeout, DNS failure, connection refused, or CORS block. That is the one
// signal available here that distinguishes "never reached/heard back from
// our backend" from a real, already-handled backend error response (which
// always carries one of the specific statuses in logSpeakError's switch
// below, never a bare 500 — VoiceSpeakView has no code path that returns a
// plain 500 for a SarvamTTSError).
const NETWORK_FAILURE_STATUS = 500;

/**
 * Returns the synthesized speech as a WAV Blob on success, or null once
 * every attempt has failed — a documented 422/429/503/504/502 error
 * envelope (see views_speak.py's own docstring for exactly which Sarvam
 * failure maps to which status) or a network/timeout failure that never
 * reached the backend at all. Every failed attempt is logged here with the
 * distinguishing status (and, for the retried class, the attempt number) so
 * a real cause is visible without reproducing the exact condition. Callers
 * must treat null exactly like "TTS unavailable right now" and fall back to
 * their own dismiss-timer — the same fail-soft contract this app's previous
 * window.speechSynthesis-based implementation always had (a synthesis
 * failure never propagates out as if the voice COMMAND itself had failed).
 */
export async function fetchSpeechAudio(text: string, language: TtsLanguage): Promise<Blob | null> {
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      const response = await clientApi.post(
        API.voice.speak,
        { text, language_code: toSarvamLanguageCode(language) },
        { responseType: "blob", timeout: SPEAK_TIMEOUT_MS },
      );
      return new Blob([response.data as BlobPart], { type: "audio/wav" });
    } catch (err: unknown) {
      const willRetry = isNetworkFailure(err) && attempt < MAX_ATTEMPTS;
      logSpeakError(err, attempt, willRetry);
      if (!willRetry) return null;
      await delay(RETRY_DELAY_MS);
    }
  }
  return null;
}

// clientApi's response interceptor already unwraps a blob-typed error body
// into normal JSON and normalizes the shape to {message, status, ...} (see
// lib/clientApi.ts's resolveBlobErrorData/normaliseError) — same shape every
// other clientApi caller in this app already reads from a caught error.
type NormalisedSpeakError = { status?: number; message?: string };

function isNetworkFailure(err: unknown): boolean {
  return (err as NormalisedSpeakError)?.status === NETWORK_FAILURE_STATUS;
}

function logSpeakError(err: unknown, attempt: number, willRetry: boolean): void {
  const e = err as NormalisedSpeakError;
  const detail = e?.message ?? String(err);
  const retryNote = willRetry
    ? ` — retrying (attempt ${attempt + 1}/${MAX_ATTEMPTS})`
    : attempt > 1
      ? ` — giving up after ${attempt} attempts`
      : "";
  switch (e?.status) {
    case 422:
      console.error(`Voice speak: request rejected (invalid text/language) — ${detail}`);
      return;
    case 429:
      console.error(`Voice speak: rate-limited — ${detail}`);
      return;
    case 503:
      console.error(`Voice speak: service unavailable — ${detail}`);
      return;
    case 504:
      console.error(`Voice speak: request timed out upstream — ${detail}`);
      return;
    case 502:
      console.error(`Voice speak: upstream error — ${detail}`);
      return;
    default:
      console.error(`Voice speak: failed — ${detail}${retryNote}`);
  }
}
