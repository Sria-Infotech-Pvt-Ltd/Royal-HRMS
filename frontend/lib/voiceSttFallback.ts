import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export interface TranscribeFallbackResult {
  transcript: string;
  languageProbability: number | null;
  wasLanguageHinted: boolean;
  detectedLanguage: "en" | "hi" | null;
}

// Pure response-shaping step, split out of captureAndTranscribeViaSarvam so
// it's testable without mocking getUserMedia/MediaRecorder/AudioContext —
// this is the one part of that function with real branching logic to get
// wrong; the rest is browser-API plumbing. Returns null exactly when the
// response carries no usable transcript (same "this retry didn't help"
// outcome captureAndTranscribeViaSarvam's own docstring documents).
export function parseTranscribeFallbackResponseData(data: {
  transcript?: string; language_probability?: number | null; was_language_hinted?: boolean;
  detected_language?: string | null;
} | undefined): TranscribeFallbackResult | null {
  const transcript = data?.transcript;
  if (typeof transcript !== "string" || !transcript.trim()) return null;
  return {
    transcript: transcript.trim(),
    languageProbability: typeof data?.language_probability === "number" ? data.language_probability : null,
    wasLanguageHinted: data?.was_language_hinted === true,
    detectedLanguage: data?.detected_language === "en" || data?.detected_language === "hi"
      ? data.detected_language
      : null,
  };
}

// A retry clip only needs to cover one short spoken command — long enough
// that a full sentence fits, short enough that the fixed-duration capture
// (there's no live transcript here to key a silence timeout off, unlike the
// browser SpeechRecognition path) doesn't feel like a hang.
//
// TRIED dynamically stopping on detected silence instead (2026-08-19, two
// real repro rounds): reverted. Real ambient-noise floor varied so much
// between takes on the same mic — sometimes true 0, sometimes 0.007-0.01 at
// rest — that a single energy threshold needed opposite corrections twice
// in one session (0.02 was too high and missed real speech entirely; 0.004
// was too low and never detected silence, defeating the point). Given real
// time pressure and that the actual root cause of failed voice commands
// turned out to be unrelated (see correction_slot_extractor.py's
// 2026-08-19 fix — "clock in karo" was being mangled AFTER transcription,
// not before it), a fixed duration is the lower-risk choice: simple,
// already proven, and not a second unresolved variable to chase.
const RECORDING_DURATION_MS = 5000;
const ENERGY_SAMPLE_INTERVAL_MS = 250;

// Mirrors useVoiceCommand.ts's TTS_CANCEL_SETTLE_MS pattern — same class of
// bug, different handoff. There, canceling speechSynthesis and starting
// SpeechRecognition in the same tick could leave recognition "started" but
// capturing nothing because the interrupted TTS output hadn't released the
// input pipeline yet. Here, this function opens a FRESH getUserMedia stream
// immediately after the browser's own SpeechRecognition session (which just
// used the mic) ended — confirmed via a real AnalyserNode energy probe
// (2026-08-17) that the newly-resolved stream carried genuine zero energy
// for its first ~750ms before any real signal appeared, even though
// getUserMedia had already resolved and permission was already granted.
// Recording starts only after this settle window elapses — with margin
// above the observed ~750ms silent window — so that dead air isn't what
// gets encoded and sent to Sarvam.
const MIC_HANDOFF_SETTLE_MS = 800;

/**
 * One-shot mic capture + Sarvam Saaras transcription — the Hindi-STT retry
 * useVoiceCommand.ts's submitTranscript falls back to only after a voice
 * transcript has already round-tripped through /voice/parse/ and come back
 * as a final no_match (both the rule engine and the sarvam-105b fallback
 * tier declined it). Saaras' translit mode (see backend/apps/voice_commands/
 * sarvam_client.py) returns a Romanized (Latin-script) transcript of
 * whatever was actually said — Hindi speech comes back as Hinglish text
 * ("muje clockin karo"), not an invented English sentence — so the caller
 * can resubmit the result through the exact same /voice/parse/ flow with no
 * language-specific handling or translation step of its own; the existing
 * intent matcher already understands Hinglish.
 *
 * Returns null on ANY failure — no mic permission, MediaRecorder/getUserMedia
 * unsupported, a network error, or Sarvam coming back with nothing usable —
 * callers must fall back to the original no-match result exactly as if this
 * retry had never been attempted.
 *
 * languageProbability is Sarvam's own confidence in which language it
 * heard, NOT a transcript-accuracy score (Sarvam doesn't expose one) — a
 * real, confirmed failure mode: identical audio resubmitted to this same
 * endpoint can return different transcripts across calls (2026-08-17). The
 * caller threads this through to /voice/parse/ as the best available proxy
 * for "is this transcript even trustworthy," per conversation.py's
 * STT-confirmation gate.
 *
 * wasLanguageHinted is true whenever this succeeded at all — both of
 * views_transcribe.py's tiers (hi-IN, then en-IN) always pass an explicit
 * language hint now, never unconstrained auto-detect — and a hinted call
 * gets no languageProbability from Sarvam at all, so the caller threads this
 * through too, as stt_used_language_hint, telling conversation.py's gate to
 * always confirm rather than skip confirmation for lack of a signal.
 *
 * detectedLanguage (Phase 4 — completes Phase 3.1's Gap 2) is the ACCURATE
 * signal wasLanguageHinted alone can't provide: which of the two tiers
 * (hi-IN vs en-IN) actually produced this transcript, forwarded verbatim
 * from views_transcribe.py's own `detected_language` field (already known
 * server-side from which sequential attempt survived — no new call). The
 * caller threads this through to /voice/parse/ as stt_detected_language,
 * which conversation.py's handle_transcript prefers over the
 * wasLanguageHinted-derived approximation for EN/HI text/voice selection —
 * it plays no part in the STT-confirmation gate, which still reads only
 * languageProbability/wasLanguageHinted (unchanged, still load-bearing there
 * per Phase 3.1's own finding).
 */
export async function captureAndTranscribeViaSarvam(): Promise<TranscribeFallbackResult | null> {
  if (
    typeof navigator === "undefined" ||
    !navigator.mediaDevices?.getUserMedia ||
    typeof MediaRecorder === "undefined"
  ) {
    return null;
  }

  let stream: MediaStream;
  try {
    // echoCancellation/noiseSuppression explicitly disabled rather than left
    // at browser defaults (on, for both, in Chrome/Edge) — tried as a theory
    // for the low RMS energy seen in captured clips, tuned for two-way calls
    // rather than offline transcription. RULED OUT for those two specifically
    // (2026-08-18): a full live testing session showed no correlation
    // between capture RMS and transcription success either way with all
    // three disabled — quiet clips succeeded, louder ones still came back
    // empty. Left disabled anyway since it's harmless and still reasonable
    // practice for STT capture.
    //
    // autoGainControl re-enabled (2026-08-19), split out from the other two:
    // a real-audio repro that day (raw Sarvam response logged server-side)
    // showed max energy of only ~0.026 even when speaking at normal volume
    // with the hi-IN hint correctly applied — language detection was right,
    // but the transcript was still short/wrong ("Huh? Go, go." for "muje
    // clockin karo"), consistent with the captured signal simply being too
    // quiet for Saaras to extract real content from, not a language problem.
    // Disabling AGC removes the browser's own gain boost on a naturally
    // quiet mic signal; re-enabling it targets that specific gap. Not yet
    // re-verified against a full live session — if hallucinated/garbled
    // transcripts persist with this on, this wasn't the (whole) fix.
    // sampleRate: 16000 matches Sarvam's own documented guidance ("works
    // best with audio sampled at 16kHz" — confirmed against real
    // docs.sarvam.ai docs, 2026-08-18); unset before, so capture ran at
    // whatever the device's default rate was (commonly 48kHz).
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true, sampleRate: 16000 },
    });
  } catch {
    return null; // permission denied, or no input device — same "can't help here" outcome
  }

  // Tap the raw stream with an AnalyserNode running IN PARALLEL with
  // MediaRecorder (both just read the same live MediaStreamTrack; neither
  // excludes the other) — passive diagnostic only, sent to the backend as
  // clientEnergyDebug so future real failures can be root-caused from
  // server logs without needing another live repro session.
  const energyReadings: number[] = [];
  let audioCtx: AudioContext | null = null;
  let energyIntervalId: ReturnType<typeof setInterval> | null = null;
  try {
    const AudioContextCtor =
      window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    audioCtx = new AudioContextCtor();
    const source = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser); // tap only — never connect(audioCtx.destination), no echo
    const buffer = new Float32Array(analyser.fftSize);
    const sampleEnergy = () => {
      analyser.getFloatTimeDomainData(buffer);
      let sumSquares = 0;
      for (let i = 0; i < buffer.length; i++) sumSquares += buffer[i] * buffer[i];
      energyReadings.push(Math.sqrt(sumSquares / buffer.length));
    };
    sampleEnergy(); // immediate reading, right when the stream resolves
    energyIntervalId = setInterval(sampleEnergy, ENERGY_SAMPLE_INTERVAL_MS);
  } catch (err) {
    console.warn("[voice-diag] energy probe failed to set up:", err);
  }

  try {
    // Wait out the mic-handoff settle window before recording starts — see
    // MIC_HANDOFF_SETTLE_MS above. The energy probe above keeps sampling
    // right through this delay, so the readings below show the settle
    // window and the actual recording in one continuous trace.
    await new Promise((resolve) => setTimeout(resolve, MIC_HANDOFF_SETTLE_MS));
    const settleReadingCount = energyReadings.length;

    const blob = await recordClip(stream);
    if (blob.size === 0) return null;

    const settleReadings = energyReadings.slice(0, settleReadingCount);
    const recordingReadings = energyReadings.slice(settleReadingCount);
    const maxEnergy = energyReadings.length ? Math.max(...energyReadings) : -1;
    const avgEnergy = energyReadings.length ? energyReadings.reduce((a, b) => a + b, 0) / energyReadings.length : -1;
    const maxDuringRecording = recordingReadings.length ? Math.max(...recordingReadings) : -1;
    const avgDuringRecording = recordingReadings.length
      ? recordingReadings.reduce((a, b) => a + b, 0) / recordingReadings.length
      : -1;

    const formData = new FormData();
    formData.append("audio", blob, "clip.webm");
    formData.append(
      "clientEnergyDebug",
      JSON.stringify({ maxEnergy, avgEnergy, maxDuringRecording, avgDuringRecording, settleReadings, recordingReadings }),
    );
    // Per-call timeout override, not clientApi's global 15000ms default —
    // same reasoning as useVoiceCommand.ts's postVoiceParse. Confirmed live
    // (2026-08-18): a real Sarvam STT call took 12.44s server-side alone
    // (sarvam_client.py's own _STT_TIMEOUT_SECONDS=10 is a per-chunk read
    // timeout, not a hard cap on total response time, so this can legally
    // run longer than that). At 12.44s the total client-observed round trip
    // (upload + Django dispatch + this call + response) can cross the 15s
    // default, causing clientApi to abort client-side while Django keeps
    // running unaware and logs a successful transcription a moment later —
    // a real transcript with no resubmit to follow it, confirmed directly
    // against that day's server log. 25000ms matches postVoiceParse's own
    // budget for the same class of problem on the sibling endpoint.
    const res = await clientApi.post(API.voice.transcribeFallback, formData, { timeout: 25000 });
    const data = (res.data as {
      data?: {
        transcript?: string; language_probability?: number | null; was_language_hinted?: boolean;
        detected_language?: string | null;
      };
    })?.data;
    return parseTranscribeFallbackResponseData(data);
  } catch {
    return null;
  } finally {
    if (energyIntervalId) clearInterval(energyIntervalId);
    if (audioCtx) void audioCtx.close().catch(() => undefined);
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
