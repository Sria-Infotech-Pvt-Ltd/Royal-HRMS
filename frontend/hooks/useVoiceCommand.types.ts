import type { TtsLanguage } from "@/lib/voiceTts";

export type NormalisedError = { message?: string };

export interface VoiceParseOutcome {
  intent: string;
  message: string;
  // TTS confidentiality — see types/voice.ts's VoiceParseResult.speech_message.
  // null for almost every intent; speak() calls fall back to `message`.
  speechMessage: string | null;
  conversational: boolean;
  awaitingInput: boolean;
  success: boolean;
  result: unknown;
  // The language THIS response's text is actually in ("en"/"hi") — see
  // types/voice.ts's VoiceParseResult.language. Defaults to "en" when absent
  // (a response built without ever reaching conversation.py's _payload, e.g.
  // a locally-constructed error) rather than leaving it undefined, so speak()
  // always has a language to request TTS in.
  language: TtsLanguage;
}

export type LocationResult = { latitude: number; longitude: number } | { errorMessage: string };

// Extra fields layered onto the base { transcript, lang } body for a silent
// resubmit of the SAME original transcript — either the geofence-retry's
// coordinates, or clock_in/clock_out's "taking facial proof" turn (see
// conversation_clock_in_face.py). Never both in the same request.
export type VoiceParseExtra = Partial<{
  latitude: number; longitude: number;
  face_embedding: number[]; liveness_passed: boolean; liveness_score: number; capture_session_id: string;
  // TEMP DIAGNOSTIC (uncommitted) — barge-in VAD energy trace. Logged
  // server-side, never used for anything.
  barge_in_debug: string;
  // Only set on a transcript from captureAndTranscribeViaSarvam (the
  // Sarvam-STT retry) — Sarvam's own confidence in which language it heard,
  // used server-side (conversation.py's STT-confirmation gate) as the best
  // available proxy for "is this transcript even trustworthy" before
  // matching/classifying it at all. Undefined for browser SpeechRecognition
  // output or typed input, which have no comparable signal.
  stt_language_probability: number;
  // Only set (true) when captureAndTranscribeViaSarvam's result came from
  // the backend's explicit-Hindi-hint attempt rather than auto-detect — that
  // mode never gets a language_probability back from Sarvam at all, so this
  // tells conversation.py's gate to confirm regardless rather than skip
  // confirmation for lack of a signal. See voiceSttFallback.ts's own
  // wasLanguageHinted docstring. Still the STT-confirmation gate's only
  // trust signal alongside stt_language_probability.
  stt_used_language_hint: boolean;
  // Phase 4 (completes Phase 3.1's Gap 2) — the accurate signal
  // stt_used_language_hint alone can't provide: which Sarvam-STT hint tier
  // (hi-IN vs en-IN) actually produced this transcript, forwarded verbatim
  // from captureAndTranscribeViaSarvam's own detectedLanguage. Additive:
  // conversation.py's handle_transcript prefers this for EN/HI text/voice
  // selection when present, but it plays no part in the STT-confirmation
  // gate above — see language.detect_language's own docstring.
  stt_detected_language: "en" | "hi";
}>;

// Marks a clock_in/clock_out response as the "taking facial proof" turn —
// mirrors conversation_clock_in_face.py's own _payload(result={'awaiting_face_proof': True}, ...).
export interface FaceProofPendingResult {
  awaiting_face_proof: boolean;
}

// "greeting": the panel opened via the keyboard toggle, before any command
// has been typed yet — never produced by this hook itself (see
// VoiceCommandButton, which renders the panel in this phase directly, ahead
// of `conversation` ever being set here). "transcript": the panel just
// opened, showing what was recognized while the request is in flight.
// "result": a response has come back — either the next turn of a
// conversational dialogue, or the final answer to a one-shot intent.
export type VoicePanelPhase = "greeting" | "transcript" | "result";
export type VoiceResultStatus = "success" | "error";

// One completed exchange — appended whenever a response actually comes
// back, never during the transient "transcript" (request in flight)
// phase. Purely additive display log for the chat-style transcript in
// VoiceConversationPanel — nothing here feeds back into the state machine
// that drives timers/TTS/dismissal.
export interface VoiceHistoryEntry {
  id: number;
  transcript: string;
  message: string;
  resultStatus: VoiceResultStatus;
}

export interface VoiceConversationState {
  transcript: string;
  message: string;
  phase: VoicePanelPhase;
  conversational: boolean;
  awaitingInput: boolean;
  // Only meaningful once phase is "result" — null while still awaiting the
  // response. Drives the checkmark/error icon for non-conversational
  // results. "error" covers both a failed /voice/parse/ request itself
  // (network, 5xx) and a recognized command that the backend rejected
  // (permission denied, a geofencing rejection that survived the retry
  // above, etc.) — see postVoiceParse's `success` field.
  resultStatus: VoiceResultStatus | null;
  // True only for clock_in/clock_out's "taking facial proof" turn (see
  // conversation_clock_in_face.py) — VoiceCommandButton opens
  // FaceVerificationModal on top of this panel when it sees this flip true,
  // and submitFaceProof is how a captured descriptor gets back in.
  awaitingFaceProof: boolean;
  // Bumped every time awaitingFaceProof turns true, including a RETRY turn
  // right after a mismatch — VoiceCommandButton keys FaceVerificationModal on
  // this so React fully remounts it (re-running its start-the-camera effect)
  // even though awaitingFaceProof itself goes true -> true across a retry
  // with no intervening false, which on its own wouldn't re-trigger a mount
  // effect keyed on isOpen alone. Without this, a retry after a mismatch
  // left the camera never reopening — surfaced once the 2026-08-13
  // matching fixes produced the first genuine voice mismatch this flow had
  // ever hit in practice.
  faceProofTurn: number;
}
