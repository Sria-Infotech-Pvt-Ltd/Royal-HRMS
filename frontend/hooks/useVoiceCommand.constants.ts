// How long to wait after the last speech update before auto-stopping —
// reset on every interim result so an actively-talking user is never cut
// off mid-sentence; only genuine silence stops the mic.
export const SILENCE_TIMEOUT_MS = 5000;

// How long the panel shows the final "done" message before closing itself
// once a conversational flow completes (awaiting_input: false). Only used
// as a fallback when nothing is actually being spoken (muted, unsupported,
// or synthesis failed to start) — see TTS_END_BUFFER_MS below for the
// normal, speech-driven case.
export const CONVERSATION_AUTO_CLOSE_MS = 4000;

// Immediate-action intents (conversational: false) are a single round trip,
// not a dialogue — the result only needs a quick glance before it closes
// itself, faster than the conversational auto-close above. Same
// muted/unsupported-only fallback caveat as CONVERSATION_AUTO_CLOSE_MS.
export const IMMEDIATE_RESULT_AUTO_CLOSE_MS = 2500;

// VC-3: how long to wait, after a mid-conversation question actually
// finishes playing, before automatically reopening the mic for the user's
// answer — a follow-up turn (slot-filling, "did you mean X?", "is that
// right?") shouldn't need a manual mic click every single turn the way a
// brand-new command does. Timed off speak()'s onEnd (the <audio> element's
// real 'ended' event — see speak() in the hook), never a fixed guess at how
// long speech takes: onEnd already fires at the correct moment regardless of
// utterance length or language, so this constant only needs to cover the
// "give the user a beat before we start listening" pause, not speech
// duration itself.
export const AUTO_LISTEN_DELAY_MS = 1000;

// If the assistant hasn't been used in this long, the next exchange starts
// a fresh chat transcript instead of tacking onto a stale one from a much
// earlier session — matches how the reference chat-widget examples behave
// (they don't accumulate history indefinitely either), while still keeping
// recent context during genuinely back-to-back use (e.g. checking leave
// balance then immediately applying for leave).
export const HISTORY_IDLE_CLEAR_MS = 10 * 60 * 1000;

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
export const TTS_END_BUFFER_MS = 400;

// ~200 words/minute — a commonly-used conservative average adult reading
// speed for UI dismiss-timing (the same ballpark toast-timing conventions
// use), not a guess. MIN_READING_TIME_MS floors even a one-word message so
// it doesn't get a near-zero read window.
export const READING_MS_PER_WORD = 300;
export const MIN_READING_TIME_MS = 1500;

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
export const VOICE_LANG = "en";
export const VOICE_LOCALE = "en-US";

// Mirrors backend apps/voice_commands/matcher.py's NO_MATCH_INTENT verbatim —
// the one outcome that triggers the Sarvam-STT retry, since it's the
// single value the rule engine AND the sarvam-105b LLM fallback tier both
// have to agree on before either gives up (see conversation.py's
// handle_transcript).
export const NO_MATCH_INTENT = "no_match";

// The two intents that ever hit PunchService.record_punch() server-side —
// only these can come back with the geofencing rejection below.
export const CLOCK_INTENTS = new Set(["clock_in", "clock_out"]);

// Mirrors backend/apps/attendance/services_geofencing.py's _validate_office
// verbatim — this is the ONE rejection reason a client-side geolocation
// retry can actually fix (the branch requires GPS and none was sent yet).
// Matched exactly, not "any failure", because other rejections from the same
// endpoint (already outside the geofence, wrong branch, permission denied,
// already clocked in, etc.) would just fail again identically with a fresh
// GPS reading — retrying those would only add a silent, pointless delay.
export const GEOFENCE_REQUIRED_MESSAGE =
  "Your location is required to clock in at this branch. Please allow location access in your browser and try again.";

// Same three strings useClockWidget.ts's manual punch flow already shows for
// these exact failure modes — reused verbatim so voice and the manual widget
// read identically to the user instead of drifting into two different
// wordings for the same underlying browser-permission problem.
export const LOCATION_UNSUPPORTED_MESSAGE = "Your browser does not support location access.";
export const LOCATION_PERMISSION_DENIED_MESSAGE =
  "Location access is required for office clock-in. Please allow location in your browser settings.";
export const LOCATION_UNAVAILABLE_MESSAGE =
  "Unable to determine your location. Please check your device's location settings and try again.";

// How long to give speechSynthesis.cancel() to actually release the audio
// pipeline before opening the mic — see startListening's beginRecognition:
// starting SpeechRecognition in the exact same tick as canceling an
// actively-playing utterance can report a "started" recognition session
// (isListening flips true, matching the UI) that never captures any audio,
// because the tail end of the interrupted TTS output hasn't released the
// input pipeline yet. Only used when something was actually speaking —
// a no-op-fast-path otherwise. Reused as-is for barge-in — startListening's
// gate is engine-agnostic (isTtsPlayingRef, not window.speechSynthesis
// directly) specifically so this same settle-delay protection applies
// whether TTS was interrupted by a manual mic press or by VAD-detected
// barge-in.
export const TTS_CANCEL_SETTLE_MS = 200;

// Barge-in VAD (voice activity detection) — same AnalyserNode/RMS technique
// as lib/voiceSttFallback.ts's mic-capture diagnostic, repurposed here to
// detect real speech ARRIVING during TTS playback instead of diagnosing
// silence after the fact. How often to sample while TTS is speaking.
//
// DISABLED (2026-08-18) — reported live as interrupting the normal
// conversation flow (opens a listening mic on every single spoken response,
// and misfires on it). Accuracy work on the base voice pipeline (STT
// non-determinism, mic capture) takes priority; barge-in stays paused until
// that's in a good place. Gated at its one call site in speak() rather
// than deleted — the VAD infrastructure (startVadTap/stopVadTap/
// handleBargeIn) is untouched so this is a one-line revert once resumed.
export const BARGE_IN_ENABLED = false;
export const BARGE_IN_SAMPLE_INTERVAL_MS = 200;

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
export const BARGE_IN_ENERGY_THRESHOLD = 0.02;

// Debounce: require this many CONSECUTIVE samples above threshold before
// declaring barge-in — a single loud transient (a door, a chair) shouldn't
// cancel a whole response. 2 samples at BARGE_IN_SAMPLE_INTERVAL_MS is a
// ~400ms reaction window; tune alongside the threshold above.
export const BARGE_IN_CONSECUTIVE_SAMPLES = 2;
