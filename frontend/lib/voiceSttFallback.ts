import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

// A retry clip only needs to cover one short spoken command — long enough
// that a full sentence fits, short enough that the fixed-duration capture
// (there's no live transcript here to key a silence timeout off, unlike the
// browser SpeechRecognition path) doesn't feel like a hang.
const RECORDING_DURATION_MS = 5000;

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
 *
 * languageProbability is Sarvam's own confidence in which language it
 * heard, NOT a transcript-accuracy score (Sarvam doesn't expose one) — a
 * real, confirmed failure mode: identical audio resubmitted to this same
 * endpoint can return different transcripts across calls (2026-08-17). The
 * caller threads this through to /voice/parse/ as the best available proxy
 * for "is this transcript even trustworthy," per conversation.py's
 * STT-confirmation gate.
 */
export async function captureAndTranscribeViaSarvam(): Promise<{
  transcript: string;
  languageProbability: number | null;
} | null> {
  if (
    typeof navigator === "undefined" ||
    !navigator.mediaDevices?.getUserMedia ||
    typeof MediaRecorder === "undefined"
  ) {
    return null;
  }

  let stream: MediaStream;
  try {
    // EXPERIMENT (uncommitted) — bare `{ audio: true }` left echoCancellation/
    // noiseSuppression/autoGainControl at the browser's own defaults (on, for
    // all three, in Chrome/Edge). The AnalyserNode probe below taps the
    // stream AFTER that processing runs, and real captured clips showed
    // energy peaking briefly then dropping near zero within the same clip —
    // the signature of a noise gate/suppressor cutting speech, not silence
    // at the source. Explicitly disabling all three here isolates whether
    // that processing (tuned for two-way calls, not offline transcription)
    // is what's actually suppressing the signal Sarvam receives. Scoped to
    // this capture only — the barge-in VAD tap (useVoiceCommand.ts's
    // startVadTap) opens its own separate stream and is untouched.
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
  } catch {
    return null; // permission denied, or no input device — same "can't help here" outcome
  }

  // TEMP DIAGNOSTIC (uncommitted) — tap the raw stream with an AnalyserNode
  // running IN PARALLEL with MediaRecorder (both just read the same live
  // MediaStreamTrack; neither excludes the other), sampled from the instant
  // getUserMedia resolves through the whole recording. This must add zero
  // delay before MediaRecorder starts — the point is to observe today's
  // exact failing timing unmodified, not to accidentally fix it by stalling
  // here. Answers: is the raw signal already silent at the source (device/
  // OS issue), or does it have real energy that's lost downstream (encoder/
  // timing issue)?
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
    energyIntervalId = setInterval(sampleEnergy, 250);
  } catch (err) {
    console.warn("[voice-diag] energy probe failed to set up:", err);
  }

  try {
    // FIX: wait out the mic-handoff settle window before recording starts —
    // see MIC_HANDOFF_SETTLE_MS above. The energy probe above keeps
    // sampling right through this delay, so the readings below show the
    // settle window and the actual recording in one continuous trace —
    // needed to confirm this fix against real energy data, not a lucky retry.
    await new Promise((resolve) => setTimeout(resolve, MIC_HANDOFF_SETTLE_MS));
    // Split point captured AFTER the wait, not before — this must count every
    // reading the setInterval above collected DURING the settle window itself,
    // not just the single synchronous t=0 sample taken before the wait even
    // started. Capturing it earlier (a bug fixed here) silently mislabeled
    // real settle-window readings as "recording" readings below.
    const settleReadingCount = energyReadings.length; // split point for before/after comparison below

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
    console.warn("[voice-diag] raw stream RMS energy (settle-delay fix applied)", {
      maxEnergy, avgEnergy, maxDuringRecording, avgDuringRecording,
      settleReadings, recordingReadings,
    });

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
    const data = (res.data as { data?: { transcript?: string; language_probability?: number | null } })?.data;
    const transcript = data?.transcript;
    if (typeof transcript !== "string" || !transcript.trim()) return null;
    return {
      transcript: transcript.trim(),
      languageProbability: typeof data?.language_probability === "number" ? data.language_probability : null,
    };
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
