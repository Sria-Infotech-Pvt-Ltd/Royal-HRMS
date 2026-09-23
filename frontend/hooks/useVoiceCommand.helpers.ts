import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { VoiceParseResult } from "@/types/voice";
import { READING_MS_PER_WORD, MIN_READING_TIME_MS, LOCATION_UNSUPPORTED_MESSAGE, LOCATION_PERMISSION_DENIED_MESSAGE, LOCATION_UNAVAILABLE_MESSAGE } from "./useVoiceCommand.constants";
import type { VoiceParseOutcome, VoiceParseExtra, LocationResult, FaceProofPendingResult } from "./useVoiceCommand.types";

export function estimateReadingTimeMs(displayedText: string): number {
  const wordCount = displayedText.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(MIN_READING_TIME_MS, wordCount * READING_MS_PER_WORD);
}

export function isAwaitingFaceProof(result: unknown): boolean {
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
export async function postVoiceParse(transcript: string, lang: string, extra?: VoiceParseExtra): Promise<VoiceParseOutcome> {
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
export function captureLocationOrErrorMessage(): Promise<LocationResult> {
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

export function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}
