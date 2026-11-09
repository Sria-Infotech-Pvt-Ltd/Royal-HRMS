// Hindi-STT retry trigger logic - pure, DOM-free core split out of
// useVoiceCommand.ts's submitTranscript/startListening, same reasoning
// voiceAutoListen.ts's own split gives: the decisions here are worth getting
// right in isolation, independently of getUserMedia/SpeechRecognition/React.

// Mirrors backend apps/voice_commands/matcher.py's NO_MATCH_INTENT verbatim.
// The single source on the frontend: hooks/useVoiceCommand.constants.ts
// re-exports it rather than defining a second copy.
export const NO_MATCH_INTENT = "no_match";

// Initial, approved starting point - NOT calibrated. Browser SpeechRecognition
// confidence varies widely by engine/OS/mic, and there is no live corpus of
// confident-vs-wrong transcripts to tune against yet. Real-device tuning is
// deferred to the final end-to-end verification.
export const LOW_CONFIDENCE_THRESHOLD = 0.5;

export interface VoiceParseOutcomeForRecovery {
  success: boolean;
  intent: string;
  // See types/voice.ts's VoiceParseResult.is_clarification.
  isClarification: boolean;
}

/**
 * Whether a completed /voice/parse/ round trip is worth silently retrying
 * through Hindi STT (captureAndTranscribeViaSarvam). True for two cases:
 *  - a genuine, final no-match: both the rule engine and the LLM fallback
 *    tier already declined the transcript server-side;
 *  - a response that matched something but only as a low/mid-confidence
 *    "did you mean X?" question (isClarification) - nothing has executed, so
 *    it is safe to discard this transcript and retry the mic capture instead
 *    of making the user sit through a clarification turn for what may have
 *    been mistranscribed Hindi.
 *
 * False for anything else, including a typed answer (sourceIsVoice=false)
 * regardless of outcome: typed text is already exactly what the user meant.
 * The caller makes at most ONE such retry per submission (the retried
 * submission is sent with sourceIsVoice=false), so recovery can never loop.
 */
export function shouldAttemptHindiRecovery(
  sourceIsVoice: boolean,
  outcome: VoiceParseOutcomeForRecovery,
): boolean {
  if (!sourceIsVoice) return false;
  const hardNoMatch = !outcome.success && outcome.intent === NO_MATCH_INTENT;
  return hardNoMatch || outcome.isClarification;
}

/**
 * Whether the browser's own per-result confidence is low enough that this
 * transcript should not be trusted with a real dispatch yet. Must be checked
 * BEFORE the first /voice/parse/ call, not after: a confident-LOOKING but
 * wrong transcript could otherwise trigger a stateful action (punch in/out,
 * a leave cancellation) before any recovery check ever runs.
 *
 * `undefined` (no confidence value at all - real-world Chromium support for
 * SpeechRecognitionAlternative.confidence is inconsistent) means "no signal",
 * never "low confidence".
 */
export function shouldDeferForLowConfidence(browserConfidence: number | undefined): boolean {
  if (browserConfidence === undefined) return false;
  return browserConfidence < LOW_CONFIDENCE_THRESHOLD;
}
