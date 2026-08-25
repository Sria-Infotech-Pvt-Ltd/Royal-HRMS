// VC-3: pure, framework/DOM-free core of the "reopen the mic after a
// mid-conversation question finishes speaking" feature — split out of
// useVoiceCommand.ts specifically so the race-prone half of it (a delayed
// timer that must yield cleanly to a manual mic click, and must not fire
// for a response a newer one has already superseded) is testable with
// fake timers in plain Node, without the jsdom/React-Testing-Library setup
// this project doesn't have (see Phase 4's own report on this same gap for
// <audio> playback timing). The DOM/React wiring around this (actually
// calling speak()/startListening(), reading utteranceTokenRef) stays in
// useVoiceCommand.ts — this module only knows about tokens and callbacks.

/**
 * Whether a just-completed, already-spoken response should trigger the
 * automatic mic reopen. True only for a genuine voice-answer follow-up
 * turn: the response's own `awaiting_input` (see backend
 * apps/voice_commands/conversation.py's _payload — pending state now
 * exists server-side, a follow-up is expected) is true, AND it isn't the
 * face-proof camera turn (conversation_clock_in_face.py's
 * awaiting_face_proof) — that turn expects a captured descriptor from
 * FaceVerificationModal, not speech, so auto-opening the mic for it would
 * be wrong regardless of awaiting_input.
 */
export function shouldAutoListenAfterSpeaking(awaitingInput: boolean, awaitingFaceProof: boolean): boolean {
  return awaitingInput && !awaitingFaceProof;
}

export interface AutoListenScheduler {
  /**
   * Arms a delayed callback for `token` — the utterance-token value that
   * was current the instant the response finished speaking. When the delay
   * elapses, `getCurrentToken()` is re-read: if it no longer matches
   * `token`, something superseded this response (a new command, an
   * explicit cancel) and the callback is skipped. Calling schedule() again
   * before a prior delay elapses replaces it — only the most recent
   * schedule can ever fire.
   */
  schedule(token: number): void;
  /** Cancels a pending delay without firing it — a no-op if none is pending. */
  cancel(): void;
}

/**
 * `getCurrentToken`/`onFire` are dependency-injected (not read from a
 * specific hook's refs) so this stays pure and independently testable.
 * `onFire` is expected to itself be idempotent/self-guarding against an
 * already-active session (useVoiceCommand's startListening() already
 * no-ops if recognition is running or about to start) — this scheduler's
 * own job is only "should this fire AT ALL", not "is it safe to act
 * twice", which is a separate, pre-existing concern this deliberately
 * doesn't duplicate.
 */
export function createAutoListenScheduler(
  getCurrentToken: () => number,
  onFire: () => void,
  delayMs: number,
): AutoListenScheduler {
  let timer: ReturnType<typeof setTimeout> | null = null;

  const cancel = (): void => {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
  };

  const schedule = (token: number): void => {
    cancel();
    timer = setTimeout(() => {
      timer = null;
      if (getCurrentToken() !== token) return; // superseded — nothing to do
      onFire();
    }, delayMs);
  };

  return { schedule, cancel };
}
