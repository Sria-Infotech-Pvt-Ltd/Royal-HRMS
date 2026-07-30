"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
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

// Once TTS is actually driving dismissal timing (not muted, synthesis
// available), the panel closes this long after the utterance's 'onend'
// fires rather than after a fixed delay — long enough for the last word to
// register, short enough not to feel stuck open.
const TTS_END_BUFFER_MS = 400;

// Single source of truth for "which language is this whole voice pipeline
// operating in" — sent to /voice/parse/ as `lang`, and used as the locale
// for both speech recognition and speech-synthesis playback, so all three
// always agree. The backend only ships an intents_en.yaml registry today
// (apps/voice_commands/registry/), so this is the only value that currently
// makes sense; when a second language's registry exists, this is the one
// place that needs to change (plus however that language gets selected).
const VOICE_LANG = "en";
const VOICE_LOCALE = "en-US";

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
  conversational: boolean;
  awaitingInput: boolean;
  success: boolean;
}

type LocationResult = { latitude: number; longitude: number } | { errorMessage: string };

// One round trip to /voice/parse/ — used for both the original submission
// and, when needed, the silent geolocation retry resubmit (same transcript
// and lang, coords added the second time only).
async function postVoiceParse(transcript: string, lang: string, coords?: { latitude: number; longitude: number }): Promise<VoiceParseOutcome> {
  const res = await clientApi.post(API.voice.parse, {
    transcript,
    lang,
    ...(coords ? { latitude: coords.latitude, longitude: coords.longitude } : {}),
  });
  const envelope = res.data as { message?: string; data?: VoiceParseResult };
  const data = envelope.data;
  return {
    intent: data?.intent ?? "",
    message: envelope.message ?? data?.message ?? "Command processed.",
    conversational: !!data?.conversational,
    awaitingInput: !!data?.awaiting_input,
    success: data?.success ?? true,
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
// a no-op-fast-path otherwise.
const TTS_CANCEL_SETTLE_MS = 200;

// "greeting": the panel opened via the keyboard toggle, before any command
// has been typed yet — never produced by this hook itself (see
// VoiceCommandButton, which renders the panel in this phase directly, ahead
// of `conversation` ever being set here). "transcript": the panel just
// opened, showing what was recognized while the request is in flight.
// "result": a response has come back — either the next turn of a
// conversational dialogue, or the final answer to a one-shot intent.
export type VoicePanelPhase = "greeting" | "transcript" | "result";
export type VoiceResultStatus = "success" | "error";

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

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const transcriptRef = useRef({ final: "", interim: "" });
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoCloseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingStartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Identifies the most recently spoken utterance — speak() cancels whatever
  // was previously playing before starting a new one, which fires the OLD
  // utterance's onerror ("interrupted") asynchronously. Without this guard,
  // that stale event would fire its onEnd callback (scheduling dismissal for
  // whatever message is on screen NOW) moments after the new message
  // replaced it, closing the panel almost immediately instead of waiting for
  // the new utterance to actually finish.
  const utteranceTokenRef = useRef(0);

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

  // Speaks the same message text shown in the panel/toast, in VOICE_LOCALE.
  // Cancels any utterance already in progress first — a new response should
  // always replace what's currently playing, never queue behind it. Wrapped
  // in try/catch because this is a nice-to-have layered on top of the
  // panel/toast text that's already visible — a synthesis failure (blocked
  // by browser policy, no voices installed, whatever) must never propagate
  // out and get mistaken for the voice command itself having failed.
  //
  // onEnd, when given, fires once this utterance actually finishes (or
  // errors out) — callers use it to tie panel dismissal to real speech
  // duration instead of a fixed timer. Returns whether speech synthesis was
  // actually attempted; false (muted, unsupported, or a synchronous
  // failure) means onEnd will never fire and the caller must fall back to
  // its own fixed-delay dismissal.
  const speak = useCallback(
    (text: string, onEnd?: () => void) => {
      if (isMuted || !text) return false;
      if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;

      try {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = VOICE_LOCALE;

        if (onEnd) {
          const token = ++utteranceTokenRef.current;
          const settle = () => {
            if (utteranceTokenRef.current === token) onEnd();
          };
          utterance.onend = settle;
          utterance.onerror = settle;
        }

        window.speechSynthesis.speak(utterance);
        return true;
      } catch (err) {
        console.error("Voice confirmation speech failed:", err);
        return false;
      }
    },
    [isMuted]
  );

  // Speaks message, then dismisses the panel — timed to the utterance's real
  // 'onend' (plus a small buffer) when TTS actually plays, falling back to
  // fixedDelayMs only when there's no audio to wait for (muted, unsupported,
  // or synthesis failed to start).
  const speakThenDismiss = useCallback(
    (message: string, fixedDelayMs: number) => {
      const isSpeaking = speak(message, () => scheduleConversationAutoClose(TTS_END_BUFFER_MS));
      if (!isSpeaking) {
        scheduleConversationAutoClose(fixedDelayMs);
      }
    },
    [speak, scheduleConversationAutoClose]
  );

  const submitTranscript = useCallback(
    async (transcript: string) => {
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
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }

      // Open the panel immediately with what was recognized, before the
      // response even comes back — same panel for every intent now, not
      // just conversational ones. Skipped only when the panel wouldn't
      // render anyway (see the isDisabled branches below, mirroring
      // VoiceCommandButton's `conversation && !isDisabled` render guard).
      if (!isDisabled) {
        setConversation({
          transcript, message: "", phase: "transcript",
          conversational: false, awaitingInput: false, resultStatus: null,
        });
      }

      try {
        let outcome = await postVoiceParse(transcript, VOICE_LANG);

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

        const { message, conversational, awaitingInput, success: isSuccess } = outcome;

        if (isDisabled) {
          // Panel can't render (e.g. the session expired mid-request) —
          // toast is the guaranteed-visible fallback for this edge case only.
          showToast(message, isSuccess ? "success" : "error");
          speak(message);
        } else {
          setConversation({
            transcript, message, phase: "result", conversational, awaitingInput,
            resultStatus: isSuccess ? "success" : "error",
          });
          if (awaitingInput) {
            // Still mid-dialogue — the question is spoken, but the panel
            // stays open waiting for the user's answer, no dismissal to time.
            speak(message);
          } else {
            // Conversational flows get the slower fixed-delay fallback (used
            // only when muted/unsupported); a one-shot result's fallback is
            // faster. Either way, real speech takes priority over both.
            speakThenDismiss(message, conversational ? CONVERSATION_AUTO_CLOSE_MS : IMMEDIATE_RESULT_AUTO_CLOSE_MS);
          }
        }
      } catch (err: unknown) {
        const e = err as NormalisedError;
        const message = e?.message ?? "Could not process the voice command. Please try again.";

        if (isDisabled) {
          showToast(message, "error");
          speak(message);
        } else {
          setConversation({
            transcript, message, phase: "result",
            conversational: false, awaitingInput: false, resultStatus: "error",
          });
          speakThenDismiss(message, IMMEDIATE_RESULT_AUTO_CLOSE_MS);
        }
      } finally {
        setStatus("idle");
        setInterimTranscript("");
      }
    },
    [showToast, clearAutoCloseTimer, speak, speakThenDismiss, isDisabled]
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
        if (event.error === "no-speech" || event.error === "aborted") {
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
          submitTranscript(transcript);
        } else {
          setStatus("idle");
          setInterimTranscript("");
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
    const synth = typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis : null;
    if (synth && (synth.speaking || synth.pending)) {
      synth.cancel();
      pendingStartTimerRef.current = setTimeout(beginRecognition, TTS_CANCEL_SETTLE_MS);
    } else {
      beginRecognition();
    }
  }, [showToast, submitTranscript, resetSilenceTimer, clearSilenceTimer]);

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
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, [clearSilenceTimer, clearAutoCloseTimer, clearPendingStartTimer]);

  return {
    status,
    interimTranscript,
    isSupported,
    isDisabled,
    startListening,
    stopListening,
    submitTranscript,
    conversation,
    closeConversation,
  };
}
