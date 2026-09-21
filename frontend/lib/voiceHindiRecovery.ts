// Hindi-STT retry trigger logic — pure, DOM-free core split out of
// useVoiceCommand.ts's submitTranscript/startListening, same reasoning
// voiceAutoListen.ts's own split docstring gives: the decisions here are
// worth getting right in isolation, independently of getUserMedia/
// SpeechRecognition/React plumbing.

// Mirrors backend apps/voice_commands/matcher.py's NO_MATCH_INTENT verbatim.
export const NO_MATCH_INTENT = "no_match";

// NOT YET CALIBRATED — starting point only, flagged for real-device
// validation the same way useVoiceCommand.ts's BARGE_IN_ENERGY_THRESHOLD was.
// Browser SpeechRecognition confidence values vary widely by engine/OS/mic,
// and this project has no live corpus of confident-vs-wrong transcripts to
// tune against yet.
export const LOW_CONFIDENCE_THRESHOLD = 0.5;

export interface VoiceParseOutcomeForRecovery {
  success: boolean;
  intent: string;
  // See types/voice.ts's VoiceParseResult.is_clarification.
  isClarification: boolean;
}

/**
 * Whether a completed /voice/parse/ round trip is worth silently retrying
 * through Hindi STT (captureAndTranscribeViaSarvam). True for two distinct
 * cases:
 *  - a genuine, final no-match: both the rule engine and the sarvam-105b
 *    fallback tier already declined the transcript server-side.
 *  - a response that DID match something, but only a low/mid-confidence
 *    "did you mean X?" clarification question (isClarification) — nothing
 *    has executed yet, so it's safe to silently discard this transcript and
 *    retry the mic capture instead of making the user sit through a
 *    clarification turn for what may have been mistranscribed Hindi.
 *
 * False for anything else, including a typed answer (sourceIsVoice=false)
 * regardless of outcome — a typed transcript is already exactly what the
 * user meant; a surprise mic capture "retrying" it would help nothing.
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
 * transcript shouldn't be trusted with a real dispatch yet. Must be checked
 * BEFORE the first /voice/parse/ call, not after — a confident-LOOKING but
 * wrong transcript could otherwise trigger a stateful action (clock in/out,
 * a leave cancellation) before any recovery check ever runs.
 *
 * `undefined` (no confidence value available at all — real-world Chromium
 * support for SpeechRecognitionAlternative.confidence is inconsistent, and
 * the ambient type declares it optional for exactly that reason — see
 * types/speechRecognition.d.ts) is treated as "no signal", never as low
 * confidence.
 */
export function shouldDeferForLowConfidence(browserConfidence: number | undefined): boolean {
  if (browserConfidence === undefined) return false;
  return browserConfidence < LOW_CONFIDENCE_THRESHOLD;
}
