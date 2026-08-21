"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import { captureAndTranscribeViaSarvam } from "@/lib/voiceSttFallback";
import { fetchSpeechAudio, type TtsLanguage } from "@/lib/voiceTts";
import type { VoiceCommandStatus, VoiceParseResult } from "@/types/voice";

type NormalisedError = { message?: string };

// How long to wait after the last speech update before auto-stopping —
// reset on every interim result so an actively-talking user is never cut
// off mid-sentence; only genuine silence stops the mic.
const SILENCE_TIMEOUT_MS = 5000;

// How long the panel shows the final "done" message before closing itself
// once a conversational flow completes (awaiting_input: false). Only used
// as a fallback when nothing is actually being spoken (muted, unsupported,
// or synthesis failed to start) — see TTS_END_BUFFER_MS below for the
// normal, speech-driven case.
const CONVERSATION_AUTO_CLOSE_MS = 4000;

// Immediate-action intents (conversational: false) are a single round trip,
// not a dialogue — the result only needs a quick glance before it closes
// itself, faster than the conversational auto-close above. Same
// muted/unsupported-only fallback caveat as CONVERSATION_AUTO_CLOSE_MS.
const IMMEDIATE_RESULT_AUTO_CLOSE_MS = 2500;

// If the assistant hasn't been used in this long, the next exchange starts
// a fresh chat transcript instead of tacking onto a stale one from a much
// earlier session — matches how the reference chat-widget examples behave
// (they don't accumulate history indefinitely either), while still keeping
// recent context during genuinely back-to-back use (e.g. checking leave
// balance then immediately applying for leave).
const HISTORY_IDLE_CLEAR_MS = 10 * 60 * 1000;

// Once TTS is actually driving dismissal timing (not muted, synthesis
// available), the panel closes this long after the utterance's 'onend'
// fires rather than after a fixed delay — long enough for the last word to
// register, short enough not to feel stuck open.
//
// BUG (2026-08-18): this alone isn't enough for intents whose spoken text is
// a short, deliberately-redacted stand-in for a much longer displayed
// message — see executor_result.py's own speech_message docstring
// (check_leave_balance/check_leave_status/payslip intents/etc. all speak a
// generic sentence like "Your leave balance is ready to view." while the
// panel shows the real figures). TTS finishes that short sentence in ~1-2s,
// so onEnd + this buffer alone closed the panel before a human could read
// the actual numbers on screen — confirmed live. estimateReadingTimeMs
// below sizes a floor off the DISPLAYED text instead, so this buffer still
// governs the common case (spoken text and displayed text are close in
// length) but never wins out over "give the reader enough time" when they
// diverge.
const TTS_END_BUFFER_MS = 400;

// ~200 words/minute — a commonly-used conservative average adult reading
// speed for UI dismiss-timing (the same ballpark toast-timing conventions
// use), not a guess. MIN_READING_TIME_MS floors even a one-word message so
// it doesn't get a near-zero read window.
const READING_MS_PER_WORD = 300;
const MIN_READING_TIME_MS = 1500;

function estimateReadingTimeMs(displayedText: string): number {
  const wordCount = displayedText.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(MIN_READING_TIME_MS, wordCount * READING_MS_PER_WORD);
}

// VOICE_LANG: sent to /voice/parse/ as `lang` — which registry to match the
// transcript against (apps/voice_commands/registry/ only ships intents_en.yaml
// today, so this is the only value that currently makes sense; when a second
// language's registry exists, this is the one place that needs to change,
// plus however that language gets selected).
//
// VOICE_LOCALE: STILL drives SpeechRecognition's own recognition.lang below
// (browser STT input) — untouched by Phase 4. It no longer has any role in
// TTS OUTPUT: speak() now sources the reply's spoken language from each
// response's own `language` field ("en"/"hi", see types/voice.ts), since a
// Hindi response needs Hindi speech regardless of what the browser's input
// recognizer is locked to.
const VOICE_LANG = "en";
const VOICE_LOCALE = "en-US";

// Mirrors backend apps/voice_commands/matcher.py's NO_MATCH_INTENT verbatim —
// the one outcome that triggers the Sarvam-STT retry below, since it's the
// single value the rule engine AND the sarvam-105b LLM fallback tier both
// have to agree on before either gives up (see conversation.py's
// handle_transcript).
const NO_MATCH_INTENT = "no_match";

// The two intents that ever hit PunchService.record_punch() server-side —
// only these can come back with the geofencing rejection below.
const CLOCK_INTENTS = new Set(["clock_in", "clock_out"]);

// Mirrors backend/apps/attendance/services_geofencing.py's _validate_office
// verbatim — this is the ONE rejection reason a client-side geolocation
// retry can actually fix (the branch requires GPS and none was sent yet).
// Matched exactly, not "any failure", because other rejections from the same
// endpoint (already outside the geofence, wrong branch, permission denied,
// already clocked in, etc.) would just fail again identically with a fresh
// GPS reading — retrying those would only add a silent, pointless delay.
const GEOFENCE_REQUIRED_MESSAGE =
  "Your location is required to clock in at this branch. Please allow location access in your browser and try again.";

// Same three strings useClockWidget.ts's manual punch flow already shows for
// these exact failure modes — reused verbatim so voice and the manual widget
// read identically to the user instead of drifting into two different
// wordings for the same underlying browser-permission problem.
const LOCATION_UNSUPPORTED_MESSAGE = "Your browser does not support location access.";
const LOCATION_PERMISSION_DENIED_MESSAGE =
  "Location access is required for office clock-in. Please allow location in your browser settings.";
const LOCATION_UNAVAILABLE_MESSAGE =
  "Unable to determine your location. Please check your device's location settings and try again.";

interface VoiceParseOutcome {
  intent: string;
  message: string;
  // TTS confidentiality — see types/voice.ts's VoiceParseResult.speech_message.
  // null for almost every intent; speak() calls below fall back to `message`.
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

type LocationResult = { latitude: number; longitude: number } | { errorMessage: string };

// Extra fields layered onto the base { transcript, lang } body for a silent
// resubmit of the SAME original transcript — either the geofence-retry's
// coordinates, or clock_in/clock_out's "taking facial proof" turn (see
// conversation_clock_in_face.py). Never both in the same request.
type VoiceParseExtra = Partial<{
  latitude: number; longitude: number;
  face_embedding: number[]; liveness_passed: boolean; liveness_score: number; capture_session_id: string;
  // TEMP DIAGNOSTIC (uncommitted) — barge-in VAD energy trace, see
  // bargeInTraceRef below. Logged server-side, never used for anything.
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
  // wasLanguageHinted docstring. UNCHANGED by Phase 4 — still the
  // STT-confirmation gate's only trust signal alongside stt_language_probability.
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
interface FaceProofPendingResult {
  awaiting_face_proof: boolean;
}

function isAwaitingFaceProof(result: unknown): boolean {
  return (
    typeof result === "object" && result !== null && "awaiting_face_proof" in result &&
    (result as FaceProofPendingResult).awaiting_face_proof === true
  );
}

// One round trip to /voice/parse/ — used for the original submission and,
// when needed, a silent resubmit of the SAME transcript with `extra` fields
// attached (a geofence retry's coordinates, or a face-proof turn's captured
// descriptor).
//
// Per-call timeout override, not clientApi's global 15000ms default: this
// endpoint's backend pipeline can fall through to sarvam-105b's chat
// completion on a genuine no-match, which is a reasoning model that
// measured (2026-08-17) up to ~17s on its "reasoning path" for a single
// short classification — backend/apps/voice_commands/sarvam_client.py's
// _CHAT_TIMEOUT_SECONDS was raised to 20s to tolerate that. clientApi's
// 15s default would then cut the frontend off before the backend's own
// (longer, intentional) budget expires, surfacing as a client-side
// "timeout of 15000ms exceeded" even though the backend was still working
// and would have answered correctly. 25s matches that 20s backend budget
// with margin, not guessed.
async function postVoiceParse(transcript: string, lang: string, extra?: VoiceParseExtra): Promise<VoiceParseOutcome> {
  const res = await clientApi.post(API.voice.parse, { transcript, lang, ...(extra ?? {}) }, { timeout: 25000 });
  const envelope = res.data as { message?: string; data?: VoiceParseResult };
  const data = envelope.data;
  return {
    intent: data?.intent ?? "",
    message: envelope.message ?? data?.message ?? "Command processed.",
    speechMessage: data?.speech_message ?? null,
    conversational: !!data?.conversational,
    awaitingInput: !!data?.awaiting_input,
    success: data?.success ?? true,
    result: data?.result,
    language: data?.language === "hi" ? "hi" : "en",
  };
}

// Same navigator.geolocation call useClockWidget.ts's office-mode branch
// makes, with the same three error strings — this is the one-time retry
// prompted by a geofencing rejection, not a proactive background capture.
function captureLocationOrErrorMessage(): Promise<LocationResult> {
  if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
    return Promise.resolve({ errorMessage: LOCATION_UNSUPPORTED_MESSAGE });
  }

  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      (geoErr: GeolocationPositionError) => {
        resolve({
          errorMessage:
            geoErr.code === 1 ? LOCATION_PERMISSION_DENIED_MESSAGE : LOCATION_UNAVAILABLE_MESSAGE,
        });
      },
      { timeout: 10000, maximumAge: 0 }
    );
  });
}

// How long to give speechSynthesis.cancel() to actually release the audio
// pipeline before opening the mic — see startListening's beginRecognition:
// starting SpeechRecognition in the exact same tick as canceling an
// actively-playing utterance can report a "started" recognition session
// (isListening flips true, matching the UI) that never captures any audio,
// because the tail end of the interrupted TTS output hasn't released the
// input pipeline yet. Only used when something was actually speaking —
// a no-op-fast-path otherwise. Reused as-is for barge-in (see handleBargeIn
// below) — startListening's gate is engine-agnostic (isTtsPlayingRef, not
// window.speechSynthesis directly) specifically so this same settle-delay
// protection applies whether TTS was interrupted by a manual mic press or
// by VAD-detected barge-in.
const TTS_CANCEL_SETTLE_MS = 200;

// Barge-in VAD (voice activity detection) — same AnalyserNode/RMS technique
// as lib/voiceSttFallback.ts's mic-capture diagnostic, repurposed here to
// detect real speech ARRIVING during TTS playback instead of diagnosing
// silence after the fact. How often to sample while TTS is speaking.
//
// DISABLED (2026-08-18) — reported live as interrupting the normal
// conversation flow (opens a listening mic on every single spoken response,
// and misfires on it). Accuracy work on the base voice pipeline (STT
// non-determinism, mic capture) takes priority; barge-in stays paused until
// that's in a good place. Gated at its one call site in speak() below rather
// than deleted — the VAD infrastructure (startVadTap/stopVadTap/
// handleBargeIn) is untouched so this is a one-line revert once resumed.
const BARGE_IN_ENABLED = false;
const BARGE_IN_SAMPLE_INTERVAL_MS = 200;

// NOT YET CALIBRATED — starting point only, per plan: must be validated
// live against real "speak over the assistant" attempts before being
// trusted, same discipline MIC_HANDOFF_SETTLE_MS in voiceSttFallback.ts
// was calibrated with. Materially different risk than that diagnostic
// though: THAT tap ran while nothing was playing through the device's own
// speakers; THIS tap runs WHILE this device's speakers are actively
// outputting the TTS audio, so the mic can pick up its own playback
// (acoustic echo) unless the browser's echo cancellation (requested below)
// actually suppresses it. Real noise floor during playback needs to be
// observed live, not assumed to match the quiet-room baseline from that
// earlier diagnostic (silence there topped out ~0.006 RMS; real speech
// there peaked ~0.22 RMS — this constant starts partway between those,
// pending real data from calibration).
const BARGE_IN_ENERGY_THRESHOLD = 0.02;

// Debounce: require this many CONSECUTIVE samples above threshold before
// declaring barge-in — a single loud transient (a door, a chair) shouldn't
// cancel a whole response. 2 samples at BARGE_IN_SAMPLE_INTERVAL_MS is a
// ~400ms reaction window; tune alongside the threshold above.
const BARGE_IN_CONSECUTIVE_SAMPLES = 2;

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
// back (see the 4 setConversation(..., phase: "result", ...) call sites
// below), never during the transient "transcript" (request in flight)
// phase. Purely additive display log for the chat-style transcript in
// VoiceConversationPanel — nothing here feeds back into the state machine
// that drives timers/TTS/dismissal above.
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
  // and submitFaceProof (below) is how a captured descriptor gets back in.
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

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

export function useVoiceCommand(isMuted: boolean, isAuthenticated: boolean) {
  const { showToast } = useToast();
  const [status, setStatus] = useState<VoiceCommandStatus>("idle");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [conversation, setConversation] = useState<VoiceConversationState | null>(null);
  // Session-only log of completed exchanges, oldest first — kept across the
  // panel closing/reopening since this hook lives in the root layout and
  // never unmounts on navigation, but reset to a clean slate (not literally
  // forever) if the assistant hasn't been used in a while — see
  // HISTORY_IDLE_CLEAR_MS below.
  const [history, setHistory] = useState<VoiceHistoryEntry[]>([]);
  const historyIdRef = useRef(0);
  const lastActivityAtRef = useRef(0);

  const appendHistory = useCallback((transcript: string, message: string, resultStatus: VoiceResultStatus) => {
    const now = Date.now();
    historyIdRef.current += 1;
    const entry: VoiceHistoryEntry = { id: historyIdRef.current, transcript, message, resultStatus };
    setHistory(prev => {
      const isStale = prev.length > 0 && now - lastActivityAtRef.current > HISTORY_IDLE_CLEAR_MS;
      return isStale ? [entry] : [...prev, entry];
    });
    lastActivityAtRef.current = now;
  }, []);

  const clearHistory = useCallback(() => setHistory([]), []);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const transcriptRef = useRef({ final: "", interim: "" });
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoCloseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingStartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Identifies the most recently spoken utterance — bumped by cancelSpeech()
  // (called at the top of every speak(), and directly whenever something
  // needs to stop TTS with no new utterance following, e.g. the mic being
  // opened). Every async step of a spoken reply (the /voice/speak/ fetch,
  // then playback) re-checks this before acting, so an utterance superseded
  // (or outright cancelled) while its network call was still in flight is
  // silently dropped instead of starting to play — and its dismissal-timing
  // onEnd callback fires at most once, for whichever utterance is actually
  // current when it settles.
  const utteranceTokenRef = useRef(0);
  // The <audio> element currently playing a spoken reply, if any — the one
  // thing cancelSpeech() needs to actually stop audible output. Replaces
  // this hook's old reliance on window.speechSynthesis.cancel() implicitly
  // stopping "whatever's playing"; there's no such single global for
  // network-fetched audio, so this hook has to track it itself.
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  // See VoiceConversationState.faceProofTurn's own docstring.
  const faceProofTurnRef = useRef(0);

  // Engine-agnostic "is TTS currently speaking" — deliberately NOT read live
  // from the playback engine itself (window.speechSynthesis.speaking,
  // startListening's gate used to read that directly; now the network-
  // fetched <audio> element's own .paused/.ended, which this ref replaces
  // for the same reason) so the exact same gate/settle-delay logic survives
  // a future engine swap unchanged. Set true right as speak() starts
  // fetching the reply's audio (not once playback literally begins — the
  // network round trip is itself something startListening's gate needs to
  // interrupt), false the moment it ends, errors, or is explicitly
  // cancelled (see cancelSpeech below).
  const isTtsPlayingRef = useRef(false);
  // Barge-in VAD tap's own resources — separate from isTtsPlayingRef itself
  // (see stopVadTap/cancelSpeech: tearing down THIS tap must not always
  // imply TTS was cancelled, e.g. on a normal utterance end there's nothing
  // left to interrupt, but nothing needs cancelling either).
  const vadStreamRef = useRef<MediaStream | null>(null);
  const vadAudioCtxRef = useRef<AudioContext | null>(null);
  const vadIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const vadAboveThresholdCountRef = useRef(0);
  // TEMP DIAGNOSTIC (uncommitted) — every reading from the MOST RECENT VAD
  // tap, reset when a new tap starts (startVadTap), NOT cleared when a tap
  // stops (stopVadTap) — so the trace survives long enough to reach
  // submitTranscript below and get attached to the /voice/parse/ call that
  // follows a barge-in, letting calibration be read from the backend log
  // directly instead of depending on DevTools console access.
  const bargeInTraceRef = useRef<Array<{ rms: number; aboveThreshold: boolean }>>([]);
  // Ref indirection so handleBargeIn (needed early, by speak()/startVadTap)
  // can call startListening (declared much later in this component, after
  // submitTranscript/attemptSilentSpeechFallback) without a declaration-
  // order cycle — kept current via a plain assignment during render right
  // after startListening is defined below.
  const startListeningRef = useRef<(() => void) | null>(null);
  const [isListeningForInterruption, setIsListeningForInterruption] = useState(false);

  const isSupported = getSpeechRecognitionConstructor() !== null;
  // Same condition VoiceCommandButton used to compute locally — centralized
  // here because submitTranscript needs it too, to know whether the panel
  // will actually render or whether the toast fallback is the only thing
  // that'll be visible (see submitTranscript below).
  const isDisabled = !isAuthenticated || !isSupported;

  const clearSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  }, []);

  // Restarts the 5s countdown — called once when listening starts and again
  // on every onresult update, so it only ever fires after genuine silence.
  const resetSilenceTimer = useCallback(() => {
    clearSilenceTimer();
    silenceTimerRef.current = setTimeout(() => {
      recognitionRef.current?.stop();
    }, SILENCE_TIMEOUT_MS);
  }, [clearSilenceTimer]);

  const clearAutoCloseTimer = useCallback(() => {
    if (autoCloseTimerRef.current) {
      clearTimeout(autoCloseTimerRef.current);
      autoCloseTimerRef.current = null;
    }
  }, []);

  const closeConversation = useCallback(() => {
    clearAutoCloseTimer();
    setConversation(null);
  }, [clearAutoCloseTimer]);

  const scheduleConversationAutoClose = useCallback(
    (delayMs: number) => {
      clearAutoCloseTimer();
      autoCloseTimerRef.current = setTimeout(() => {
        setConversation(null);
      }, delayMs);
    },
    [clearAutoCloseTimer]
  );

  // Tears down the VAD tap's OWN resources only — deliberately does not
  // touch isTtsPlayingRef. Called both when TTS ends normally (nothing left
  // to interrupt) and as part of cancelSpeech (something else is stopping
  // TTS anyway) — idempotent so either caller can call it freely.
  const stopVadTap = useCallback(() => {
    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }
    if (vadAudioCtxRef.current) {
      void vadAudioCtxRef.current.close().catch(() => undefined);
      vadAudioCtxRef.current = null;
    }
    if (vadStreamRef.current) {
      vadStreamRef.current.getTracks().forEach((track) => track.stop());
      vadStreamRef.current = null;
    }
    vadAboveThresholdCountRef.current = 0;
    setIsListeningForInterruption(false);
  }, []);

  // Fired once VAD sees BARGE_IN_CONSECUTIVE_SAMPLES in a row above
  // threshold. Deliberately does NOT itself cancel TTS or apply a settle
  // delay — it tears down only this tap's own resources, then calls
  // startListening(), whose existing gate (below) is what actually checks
  // isTtsPlayingRef, cancels speech, and waits out TTS_CANCEL_SETTLE_MS
  // before opening the real capture mic. Reusing that gate verbatim is the
  // whole point: it's the exact same handoff-timing protection already
  // proven for a manual mic press during TTS playback, not a new, separately-
  // risked code path.
  const handleBargeIn = useCallback((token: number) => {
    // Stale tap — a newer utterance already superseded this one, or TTS
    // already ended normally before this fired. Nothing to interrupt.
    if (utteranceTokenRef.current !== token || !isTtsPlayingRef.current) return;
    stopVadTap();
    startListeningRef.current?.();
  }, [stopVadTap]);

  // Opens a mic stream purely to watch for barge-in while `token`'s
  // utterance plays — never used to capture the actual interrupting
  // command itself (that's startListening's job, via handleBargeIn above).
  // Fire-and-forget: speak() is synchronous and must not await mic
  // permission before starting TTS, so failure here (no permission, no
  // input device) just means barge-in isn't available for this utterance —
  // TTS still plays normally, same as before this feature existed.
  const startVadTap = useCallback((token: number) => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) return;
    const AudioContextCtor =
      typeof window !== "undefined"
        ? window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
        : undefined;
    if (!AudioContextCtor) return;

    navigator.mediaDevices
      .getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      .then((stream) => {
        // The utterance this tap was opened for may already have ended (or
        // been superseded by a newer one) by the time permission resolves —
        // don't attach a tap to a response that's no longer playing.
        if (utteranceTokenRef.current !== token || !isTtsPlayingRef.current) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        const audioCtx = new AudioContextCtor();
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 2048;
        source.connect(analyser); // tap only — never connect(audioCtx.destination)

        vadStreamRef.current = stream;
        vadAudioCtxRef.current = audioCtx;
        vadAboveThresholdCountRef.current = 0;
        bargeInTraceRef.current = []; // fresh trace for this tap — see its own declaration
        setIsListeningForInterruption(true);

        const buffer = new Float32Array(analyser.fftSize);
        vadIntervalRef.current = setInterval(() => {
          analyser.getFloatTimeDomainData(buffer);
          let sumSquares = 0;
          for (let i = 0; i < buffer.length; i++) sumSquares += buffer[i] * buffer[i];
          const rms = Math.sqrt(sumSquares / buffer.length);
          const aboveThreshold = rms >= BARGE_IN_ENERGY_THRESHOLD;

          // TEMP DIAGNOSTIC (uncommitted) — every reading while TTS plays,
          // to calibrate BARGE_IN_ENERGY_THRESHOLD/BARGE_IN_CONSECUTIVE_SAMPLES
          // against real speak-over-TTS attempts. Recorded here (read from
          // the backend log via submitTranscript's barge_in_debug attach
          // below) rather than relying only on the console.warn line, which
          // needs DevTools open on the tester's own machine to see.
          bargeInTraceRef.current.push({ rms, aboveThreshold });
          console.warn(
            "[barge-in-diag] rms=%s consecutive=%d threshold=%s",
            rms.toFixed(4), vadAboveThresholdCountRef.current, BARGE_IN_ENERGY_THRESHOLD
          );

          if (aboveThreshold) {
            vadAboveThresholdCountRef.current += 1;
          } else {
            vadAboveThresholdCountRef.current = 0;
          }

          if (vadAboveThresholdCountRef.current >= BARGE_IN_CONSECUTIVE_SAMPLES) {
            handleBargeIn(token);
          }
        }, BARGE_IN_SAMPLE_INTERVAL_MS);
      })
      .catch(() => {
        // No mic permission / no input device — barge-in unavailable for
        // this utterance; TTS just plays normally, same as always.
      });
  }, [handleBargeIn]);

  // Single, engine-swappable "stop whatever is speaking" entry point — every
  // TTS-cancel call site in this hook goes through this rather than reaching
  // into the playback engine directly, so a future TTS engine swap only
  // needs to change this one function's body. Bumps utteranceTokenRef so
  // ANY earlier utterance's still-in-flight /voice/speak/ fetch or scheduled
  // playback is recognized as stale and dropped when it resolves (see
  // speak() below) — network-fetched audio has no single global "cancel
  // whatever's playing" the way window.speechSynthesis.cancel() was, so this
  // hook has to track and stop it explicitly. Always tears down the VAD tap
  // too: if speech is being cancelled for any reason, there's nothing left
  // to guard against barging in on.
  const cancelSpeech = useCallback(() => {
    utteranceTokenRef.current += 1;
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      URL.revokeObjectURL(currentAudioRef.current.src);
      currentAudioRef.current = null;
    }
    isTtsPlayingRef.current = false;
    stopVadTap();
  }, [stopVadTap]);

  // Speaks the same message text shown in the panel/toast, via POST
  // /api/voice/speak/ (Sarvam Bulbul TTS, always voiced as "shubh"
  // server-side) in `language` — the response's own detected language
  // ("en"/"hi"), NOT VOICE_LOCALE (that constant only drives STT's
  // recognition.lang now — see its own comment). Cancels any utterance
  // already in progress first — a new response should always replace what's
  // currently playing, never queue behind it.
  //
  // onEnd, when given, fires once this utterance actually finishes playing,
  // fails to play, or the /voice/speak/ call itself fails — callers use it
  // to tie panel dismissal to real speech duration instead of a fixed timer,
  // and rely on it always eventually firing (never left hanging) so long as
  // this returns true. Returns whether playback was actually attempted;
  // false (muted or empty text — the only synchronous no-op cases) means
  // onEnd will never fire and the caller must fall back to its own
  // fixed-delay dismissal.
  const speak = useCallback(
    (text: string, language: TtsLanguage, onEnd?: () => void) => {
      if (isMuted || !text) return false;

      cancelSpeech(); // stop whatever was playing (and its VAD tap) first, bumping the token
      const token = utteranceTokenRef.current;
      isTtsPlayingRef.current = true;

      // Unconditional now (not gated on `onEnd` being passed) — every
      // utterance needs isTtsPlayingRef/the VAD tap cleared when it ends,
      // regardless of whether the caller also wanted an onEnd callback.
      const settle = () => {
        if (utteranceTokenRef.current === token) {
          isTtsPlayingRef.current = false;
          stopVadTap();
          onEnd?.();
        }
      };

      void fetchSpeechAudio(text, language).then((blob) => {
        // Superseded (or outright cancelled) while the network call was in
        // flight — cancelSpeech() already bumped the token for whatever
        // superseded this. Never start playing stale audio, and never call
        // settle() for it either: the utterance that superseded this one
        // owns dismissal timing now.
        if (utteranceTokenRef.current !== token) return;
        if (!blob) {
          // fetchSpeechAudio already logged the distinguishing 422/429/503/
          // 504/502/network reason — settle() here is the "fall back to the
          // existing dismiss-timer behavior so nothing hangs" half of that
          // failure handling (see speakThenDismiss's own onEnd, which sizes
          // its delay off the DISPLAYED text's reading time, not a guess).
          settle();
          return;
        }

        try {
          const blobUrl = URL.createObjectURL(blob);
          const audio = new Audio(blobUrl);
          currentAudioRef.current = audio;
          const finish = () => {
            URL.revokeObjectURL(blobUrl);
            if (currentAudioRef.current === audio) currentAudioRef.current = null;
            settle();
          };
          audio.onended = finish;
          audio.onerror = finish;

          if (BARGE_IN_ENABLED) startVadTap(token);
          audio.play().catch((err) => {
            console.error("Voice speak: playback failed —", err);
            finish();
          });
        } catch (err) {
          // Belt-and-suspenders — Audio()/createObjectURL essentially never
          // throw, but this is a nice-to-have layered on top of the
          // panel/toast text that's already visible, same reasoning this
          // hook's old speechSynthesis try/catch gave: a synthesis/playback
          // failure must never propagate out as if the voice COMMAND itself
          // had failed, and must never leave the caller hanging without
          // settle() ever firing.
          console.error("Voice speak: could not start playback —", err);
          settle();
        }
      });

      return true;
    },
    [isMuted, cancelSpeech, stopVadTap, startVadTap]
  );

  // Speaks spokenText in `language`, then dismisses the panel — timed to the
  // utterance's real end (plus a floor sized to how long displayedText
  // actually takes to READ, not just how long spokenText takes to SAY) when
  // TTS actually plays (successfully or not — see speak()'s own settle()),
  // falling back to fixedDelayMs (with the same reading floor applied) only
  // when there's no audio attempt to wait for at all (muted or empty text).
  //
  // spokenText and displayedText are the same string for most intents, but
  // deliberately diverge for confidentiality-redacted ones (see
  // TTS_END_BUFFER_MS's own comment) — displayedText is always what the
  // panel actually shows, so it's always what dismiss timing must respect.
  const speakThenDismiss = useCallback(
    (spokenText: string, fixedDelayMs: number, displayedText: string, language: TtsLanguage) => {
      const readingFloorMs = estimateReadingTimeMs(displayedText);
      const isSpeaking = speak(
        spokenText, language, () => scheduleConversationAutoClose(Math.max(TTS_END_BUFFER_MS, readingFloorMs))
      );
      if (!isSpeaking) {
        scheduleConversationAutoClose(Math.max(fixedDelayMs, readingFloorMs));
      }
    },
    [speak, scheduleConversationAutoClose]
  );

  const submitTranscript = useCallback(
    async (
      transcript: string, sourceIsVoice: boolean = false,
      sttLanguageProbability?: number | null, sttUsedLanguageHint: boolean = false,
      sttDetectedLanguage?: "en" | "hi" | null
    ) => {
      setStatus("processing");
      clearAutoCloseTimer();

      // Stop any question still being read aloud before replacing what's on
      // screen. The voice-answer path (startListening's beginRecognition)
      // already cancels playback before it ever opens the mic, so by the
      // time recognition hands a transcript to this function nothing is
      // speaking. But this function is also called directly by the typed-
      // answer input, which has no such guard — without this, submitting an
      // answer while a long question is still playing blanks the panel's
      // text immediately while the old utterance keeps talking, audibly out
      // of sync with what's on screen.
      cancelSpeech();

      // Open the panel immediately with what was recognized, before the
      // response even comes back — same panel for every intent now, not
      // just conversational ones. Skipped only when the panel wouldn't
      // render anyway (see the isDisabled branches below, mirroring
      // VoiceCommandButton's `conversation && !isDisabled` render guard).
      if (!isDisabled) {
        setConversation({
          transcript, message: "", phase: "transcript",
          conversational: false, awaitingInput: false, resultStatus: null, awaitingFaceProof: false,
          faceProofTurn: faceProofTurnRef.current,
        });
      }

      // TEMP DIAGNOSTIC (uncommitted) — attach the just-completed VAD tap's
      // energy trace (see bargeInTraceRef) to this submission only when it
      // came from the mic (sourceIsVoice) and a trace actually exists (TTS
      // was genuinely playing beforehand) — read back from the backend log
      // apps/voice_commands/views.py logs it to, for calibration without
      // needing DevTools console access on the tester's machine. Cleared
      // immediately after building the payload so it can't leak onto a
      // later, unrelated submission.
      const bargeInDebugExtra =
        sourceIsVoice && bargeInTraceRef.current.length > 0
          ? { barge_in_debug: JSON.stringify(bargeInTraceRef.current) }
          : undefined;
      bargeInTraceRef.current = [];

      // Only set when this transcript came from captureAndTranscribeViaSarvam
      // (attemptSilentSpeechFallback's retry) — see VoiceParseExtra's own
      // comment on stt_language_probability.
      const firstCallExtra = {
        ...bargeInDebugExtra,
        ...(sttLanguageProbability != null ? { stt_language_probability: sttLanguageProbability } : {}),
        ...(sttUsedLanguageHint ? { stt_used_language_hint: true } : {}),
        ...(sttDetectedLanguage ? { stt_detected_language: sttDetectedLanguage } : {}),
      };

      try {
        let outcome = await postVoiceParse(
          transcript, VOICE_LANG,
          Object.keys(firstCallExtra).length > 0 ? firstCallExtra : undefined,
        );
        // What the result panel actually shows/acts on — starts as the raw
        // browser transcript, replaced below only if the Sarvam-STT retry
        // fires and comes back with something usable.
        let displayTranscript = transcript;

        // Voice never collects GPS up front (unlike the manual ClockWidget,
        // which only asks when mode is office) — so an office-mode clock_in/
        // clock_out with no coordinates yet hits this exact rejection on the
        // first attempt whenever the employee's branch requires geofencing.
        // Rather than making the user repeat the whole command, fetch the
        // location now and silently resubmit the identical transcript once.
        if (!outcome.success && CLOCK_INTENTS.has(outcome.intent) && outcome.message === GEOFENCE_REQUIRED_MESSAGE) {
          const located = await captureLocationOrErrorMessage();
          if ("errorMessage" in located) {
            outcome = { ...outcome, message: located.errorMessage };
          } else {
            outcome = await postVoiceParse(transcript, VOICE_LANG, located);
          }
        }

        // Hindi-STT retry: only for a transcript that actually came from the
        // mic (a typed answer is already exactly what the user meant — a
        // surprise mic capture "retrying" it would help nothing) and only on
        // a genuine, final no-match, meaning both the rule engine and the
        // sarvam-105b classification tier already declined it server-side
        // (see backend conversation.py's handle_transcript). The browser's
        // Web Speech API is unreliable for Hindi; this is the one silent
        // recovery attempt for "that transcript might have been garbled
        // Hindi, not just an unmatched English phrase" before showing the
        // normal failure. Exactly one retry — if Sarvam can't help either,
        // or the resubmitted transcript still no-matches, everything below
        // behaves exactly as if this retry had never been attempted.
        if (sourceIsVoice && !outcome.success && outcome.intent === NO_MATCH_INTENT) {
          const sarvamResult = await captureAndTranscribeViaSarvam();
          if (sarvamResult) {
            displayTranscript = sarvamResult.transcript;
            outcome = await postVoiceParse(sarvamResult.transcript, VOICE_LANG, {
              stt_language_probability: sarvamResult.languageProbability ?? undefined,
              ...(sarvamResult.wasLanguageHinted ? { stt_used_language_hint: true } : {}),
              ...(sarvamResult.detectedLanguage ? { stt_detected_language: sarvamResult.detectedLanguage } : {}),
            });
          }
        }

        const { message, speechMessage, conversational, awaitingInput, success: isSuccess } = outcome;
        // TTS confidentiality: sensitive intents (payslip figures, leave
        // balances/dates, another employee's leave type) supply a redacted
        // speechMessage — spoken instead of `message` regardless of the mute
        // toggle's state, so this is conservative by default rather than
        // only when the user already muted everything. The panel/toast below
        // always renders the full `message`, never spokenText.
        const spokenText = speechMessage ?? message;

        // Notify ClockWidget and dashboard consoles immediately on success —
        // don't wait for the WebSocket path which requires Daphne to be up.
        if (isSuccess && CLOCK_INTENTS.has(outcome.intent)) {
          window.dispatchEvent(new CustomEvent("attendance:updated"));
        }
        // Leave approvals: no direct dispatch — the backend pushes fresh counts
        // through the WebSocket (overview.py:push_leave_update) with the full
        // action_queue payload, so components update state directly from the WS
        // frame without an HTTP refetch.

        if (isDisabled) {
          // Panel can't render (e.g. the session expired mid-request) —
          // toast is the guaranteed-visible fallback for this edge case only.
          showToast(message, isSuccess ? "success" : "error");
          speak(spokenText, outcome.language);
        } else {
          const awaitingFaceProof = awaitingInput && isAwaitingFaceProof(outcome.result);
          if (awaitingFaceProof) faceProofTurnRef.current += 1;
          setConversation({
            transcript: displayTranscript, message, phase: "result", conversational, awaitingInput,
            resultStatus: isSuccess ? "success" : "error",
            awaitingFaceProof, faceProofTurn: faceProofTurnRef.current,
          });
          appendHistory(displayTranscript, message, isSuccess ? "success" : "error");
          if (awaitingInput) {
            // Still mid-dialogue — the question is spoken, but the panel
            // stays open waiting for the user's answer, no dismissal to time.
            speak(spokenText, outcome.language);
          } else {
            // Conversational flows get the slower fixed-delay fallback (used
            // only when muted or /voice/speak/ failed); a one-shot result's
            // fallback is faster. Either way, real speech takes priority over both.
            speakThenDismiss(
              spokenText, conversational ? CONVERSATION_AUTO_CLOSE_MS : IMMEDIATE_RESULT_AUTO_CLOSE_MS, message,
              outcome.language
            );
          }
        }
      } catch (err: unknown) {
        const e = err as NormalisedError;
        const message = e?.message ?? "Could not process the voice command. Please try again.";

        // A locally-constructed English string (the /voice/parse/ call itself
        // failed, so there's no backend `language` field to read) — spoken in
        // English, same as before this response ever had a language of its own.
        if (isDisabled) {
          showToast(message, "error");
          speak(message, "en");
        } else {
          setConversation({
            transcript, message, phase: "result",
            conversational: false, awaitingInput: false, resultStatus: "error", awaitingFaceProof: false,
            faceProofTurn: faceProofTurnRef.current,
          });
          appendHistory(transcript, message, "error");
          speakThenDismiss(message, IMMEDIATE_RESULT_AUTO_CLOSE_MS, message, "en");
        }
      } finally {
        setStatus("idle");
        setInterimTranscript("");
      }
    },
    [showToast, clearAutoCloseTimer, speak, speakThenDismiss, isDisabled, cancelSpeech, appendHistory]
  );

  // Browser SpeechRecognition is locked to VOICE_LOCALE ("en-US") — genuine
  // non-English speech (Hindi included) often isn't garbled-transcribed into
  // SOME (wrong) English text the way a near-miss English phrase would be;
  // Chrome commonly recognizes it as no speech at all and fires a "no-speech"
  // error, or ends with an empty final transcript, before submitTranscript is
  // ever called. submitTranscript's own Sarvam-STT retry (the NO_MATCH_INTENT
  // branch above) can only fire on a transcript that actually round-tripped
  // through /voice/parse/ — it never gets a chance if nothing was ever
  // submitted. This is the fallback for THAT case: browser recognition came
  // back with literally nothing usable, so try Sarvam Saaras directly rather
  // than silently giving up. sourceIsVoice=false on the resubmit — this
  // already used the one Sarvam attempt; a no_match on its result shouldn't
  // chain into opening the mic a third time.
  const attemptSilentSpeechFallback = useCallback(async () => {
    setStatus("processing");
    showToast("Didn't catch that — trying once more…", "success");
    const sarvamResult = await captureAndTranscribeViaSarvam();
    if (sarvamResult) {
      await submitTranscript(
        sarvamResult.transcript, false, sarvamResult.languageProbability, sarvamResult.wasLanguageHinted,
        sarvamResult.detectedLanguage
      );
    } else {
      showToast("Voice recognition error. Please try again.", "error");
      setStatus("idle");
      setInterimTranscript("");
    }
  }, [showToast, submitTranscript]);

  // Second+ turn of the clock_in/clock_out facial-proof dialogue —
  // VoiceCommandButton calls this once FaceVerificationModal produces a
  // captured descriptor, resubmitting the SAME original transcript
  // (conversation.transcript) with it attached, exactly like the geofence
  // retry above resubmits it with coordinates. Never called unless
  // conversation.awaitingFaceProof is already true, so `conversation` is
  // always non-null in practice; the guard is defensive only.
  const submitFaceProof = useCallback(
    async (embedding: number[], livenessScore: number, captureSessionId: string) => {
      if (!conversation) return;
      const transcript = conversation.transcript;
      setStatus("processing");
      clearAutoCloseTimer();

      try {
        const outcome = await postVoiceParse(transcript, VOICE_LANG, {
          face_embedding: embedding, liveness_passed: true,
          liveness_score: livenessScore, capture_session_id: captureSessionId,
        });
        const { message, speechMessage, conversational, awaitingInput, success: isSuccess } = outcome;
        const spokenText = speechMessage ?? message;

        if (isSuccess && CLOCK_INTENTS.has(outcome.intent)) {
          window.dispatchEvent(new CustomEvent("attendance:updated"));
        }

        const awaitingFaceProof = awaitingInput && isAwaitingFaceProof(outcome.result);
        if (awaitingFaceProof) faceProofTurnRef.current += 1;
        setConversation({
          transcript, message, phase: "result", conversational, awaitingInput,
          resultStatus: isSuccess ? "success" : "error",
          awaitingFaceProof, faceProofTurn: faceProofTurnRef.current,
        });
        appendHistory(transcript, message, isSuccess ? "success" : "error");
        if (awaitingInput) {
          speak(spokenText, outcome.language);
        } else {
          speakThenDismiss(
            spokenText, conversational ? CONVERSATION_AUTO_CLOSE_MS : IMMEDIATE_RESULT_AUTO_CLOSE_MS, message,
            outcome.language
          );
        }
      } catch (err: unknown) {
        const e = err as NormalisedError;
        const message = e?.message ?? "Could not verify your face. Please try again.";
        setConversation({
          transcript, message, phase: "result",
          conversational: false, awaitingInput: false, resultStatus: "error", awaitingFaceProof: false,
          faceProofTurn: faceProofTurnRef.current,
        });
        appendHistory(transcript, message, "error");
        // Locally-constructed English string (the /voice/parse/ call itself
        // failed) — same reasoning as submitTranscript's own catch block.
        speakThenDismiss(message, IMMEDIATE_RESULT_AUTO_CLOSE_MS, message, "en");
      } finally {
        setStatus("idle");
      }
    },
    [conversation, clearAutoCloseTimer, speak, speakThenDismiss, appendHistory]
  );

  const clearPendingStartTimer = useCallback(() => {
    if (pendingStartTimerRef.current) {
      clearTimeout(pendingStartTimerRef.current);
      pendingStartTimerRef.current = null;
    }
  }, []);

  const startListening = useCallback(() => {
    if (recognitionRef.current || pendingStartTimerRef.current) return; // already listening / about to

    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) {
      showToast("Voice commands aren't supported in this browser. Try Chrome or Edge.", "error");
      return;
    }

    const beginRecognition = () => {
      pendingStartTimerRef.current = null;

      const recognition = new Recognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = VOICE_LOCALE;

      transcriptRef.current = { final: "", interim: "" };
      setInterimTranscript("");

      recognition.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const piece = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            transcriptRef.current.final += piece;
          } else {
            interim += piece;
          }
        }
        transcriptRef.current.interim = interim;
        setInterimTranscript((transcriptRef.current.final + interim).trim());
        resetSilenceTimer(); // new speech detected — push the auto-stop back out
      };

      recognition.onerror = (event) => {
        clearSilenceTimer();
        recognitionRef.current = null;
        if (event.error === "no-speech") {
          // Browser detected literally no en-US-recognizable speech — the
          // common case for genuine non-English audio (see
          // attemptSilentSpeechFallback's own comment). "aborted" (below)
          // stays a silent no-op: that's the user's own deliberate stop, not
          // a failed recognition worth retrying.
          void attemptSilentSpeechFallback();
          return;
        }
        if (event.error === "aborted") {
          setStatus("idle");
          setInterimTranscript("");
          return;
        }
        showToast("Voice recognition error. Please try again.", "error");
        setStatus("idle");
        setInterimTranscript("");
      };

      recognition.onend = () => {
        clearSilenceTimer();
        recognitionRef.current = null;
        const transcript = (transcriptRef.current.final || transcriptRef.current.interim).trim();
        if (transcript) {
          // sourceIsVoice=true — this transcript came from the mic, so a
          // final no-match is eligible for the Sarvam-STT retry (see
          // submitTranscript's own comment on that branch).
          submitTranscript(transcript, true);
        } else {
          // Recognition ended (e.g. the silence timeout fired) with nothing
          // usable ever recognized — same non-English-speech case onerror's
          // "no-speech" branch handles, just surfacing through onend instead
          // of onerror depending on the browser.
          void attemptSilentSpeechFallback();
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
      setStatus("listening");
      resetSilenceTimer(); // start the countdown even if the user says nothing at all
    };

    // Stop any confirmation still playing before opening the mic — otherwise
    // recognition would pick up the assistant's own voice as input. Only
    // defer the actual recognition.start() when something was genuinely
    // speaking: canceling an in-progress utterance and starting
    // SpeechRecognition in the exact same tick can leave the recognition
    // session reporting "started" (this hook's status flips to "listening",
    // same as a real start) while never actually capturing audio, because
    // the interrupted TTS output hasn't released the input pipeline yet.
    // Nothing to defer in the common case (user waits for the question to
    // finish before answering), so this stays a same-tick start then.
    //
    // Checked via isTtsPlayingRef, not window.speechSynthesis directly, so
    // this exact gate also protects the barge-in handoff (handleBargeIn
    // calls startListening() while isTtsPlayingRef is still true) — same
    // settle-delay protection, same code path, not a second one to keep in
    // sync.
    if (isTtsPlayingRef.current) {
      cancelSpeech();
      pendingStartTimerRef.current = setTimeout(beginRecognition, TTS_CANCEL_SETTLE_MS);
    } else {
      beginRecognition();
    }
  }, [showToast, submitTranscript, attemptSilentSpeechFallback, resetSilenceTimer, clearSilenceTimer, cancelSpeech]);

  // Breaks the declaration-order cycle noted at startListeningRef's own
  // declaration above. A ref write belongs in an effect, not render body
  // (React: refs must not be read/written during render) — the one-render
  // lag this implies is harmless here, since handleBargeIn only ever reads
  // this ref later, from an async interval callback, never synchronously
  // during the render that just defined startListening.
  useEffect(() => {
    startListeningRef.current = startListening;
  }, [startListening]);

  const stopListening = useCallback(() => {
    // Cancels a still-pending deferred start (see startListening) as well as
    // an already-active recognition — either way, the user asked to stop.
    clearPendingStartTimer();
    recognitionRef.current?.stop();
  }, [clearPendingStartTimer]);

  // Abort any in-flight recognition, pending timers, and playing confirmation
  // on unmount (e.g. navigating away mid-listen).
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      clearSilenceTimer();
      clearAutoCloseTimer();
      clearPendingStartTimer();
      cancelSpeech();
    };
  }, [clearSilenceTimer, clearAutoCloseTimer, clearPendingStartTimer, cancelSpeech]);

  return {
    status,
    interimTranscript,
    isSupported,
    isDisabled,
    startListening,
    stopListening,
    submitTranscript,
    submitFaceProof,
    conversation,
    closeConversation,
    // Visible "listening for interruption" indicator — true only while a
    // VAD tap is actually open (i.e. TTS is speaking AND mic permission for
    // the tap succeeded). Per plan: the mic being live during every spoken
    // response must be visible to the user, not silent.
    isListeningForInterruption,
    // Session-only chat transcript — see VoiceHistoryEntry.
    history,
    clearHistory,
  };
}
