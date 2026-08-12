import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

// A retry clip only needs to cover one short spoken command — long enough
// that a full sentence fits, short enough that the fixed-duration capture
// (there's no live transcript here to key a silence timeout off, unlike the
// browser SpeechRecognition path) doesn't feel like a hang.
const RECORDING_DURATION_MS = 5000;

/**
 * One-shot mic capture + Sarvam Saaras transcription — the Hindi-STT retry
 * useVoiceCommand.ts's submitTranscript falls back to only after a voice
 * transcript has already round-tripped through /voice/parse/ and come back
 * as a final no_match (both the rule engine and the sarvam-105b fallback
 * tier declined it). Saaras' translate mode (see backend/apps/voice_commands/
 * sarvam_client.py) auto-detects the spoken language — English or any of 22
 * Indic languages, Hindi included — and always returns English text, so the
 * caller can resubmit the result through the exact same /voice/parse/ flow
 * with no language-specific handling of its own.
 *
 * Returns null on ANY failure — no mic permission, MediaRecorder/getUserMedia
 * unsupported, a network error, or Sarvam coming back with nothing usable —
 * callers must fall back to the original no-match result exactly as if this
 * retry had never been attempted.
 */
export async function captureAndTranscribeViaSarvam(): Promise<string | null> {
  if (
    typeof navigator === "undefined" ||
    !navigator.mediaDevices?.getUserMedia ||
    typeof MediaRecorder === "undefined"
  ) {
    return null;
  }

  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    return null; // permission denied, or no input device — same "can't help here" outcome
  }

  try {
    const blob = await recordClip(stream);
    if (blob.size === 0) return null;

    const formData = new FormData();
    formData.append("audio", blob, "clip.webm");
    const res = await clientApi.post(API.voice.transcribeFallback, formData);
    const transcript = (res.data as { data?: { transcript?: string } })?.data?.transcript;
    return typeof transcript === "string" && transcript.trim() ? transcript.trim() : null;
  } catch {
    return null;
  } finally {
    stream.getTracks().forEach((track) => track.stop());
  }
}

function recordClip(stream: MediaStream): Promise<Blob> {
  return new Promise((resolve, reject) => {
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream);
    } catch (err) {
      reject(err);
      return;
    }

    const chunks: BlobPart[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
    recorder.onerror = () => reject(new Error("MediaRecorder error"));

    recorder.start();
    setTimeout(() => {
      if (recorder.state !== "inactive") recorder.stop();
    }, RECORDING_DURATION_MS);
  });
}
