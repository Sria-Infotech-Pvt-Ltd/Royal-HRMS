// Runs a background poll only while the login session is alive. Once the session is known to have expired (a refresh
// failed), polling stops for good: every further poll would only be a request the server answers with 401, and the app is
// about to send the person to the login page. The dependencies are passed in so this can be tested without a browser.
export interface SessionPollDeps {
  /** True once the session is known to be over. */
  isExpired: () => boolean;
  /** Subscribes to the session-expired event; returns an unsubscribe. */
  onExpired: (listener: () => void) => () => void;
}

/**
 * Polls now and then every `intervalMs`, until the session expires or the returned function is called.
 * Starts nothing if the session is already known to be expired.
 */
export function pollWhileSessionLive(poll: () => void, intervalMs: number, deps: SessionPollDeps): () => void {
  if (deps.isExpired()) return () => {};
  let timer: ReturnType<typeof setInterval> | null = null;
  let unsubscribe: (() => void) | null = null;

  function stop() {
    if (timer !== null) clearInterval(timer);
    timer = null;
    if (unsubscribe) unsubscribe();
    unsubscribe = null;
  }

  unsubscribe = deps.onExpired(stop);
  poll();
  timer = setInterval(() => {
    if (deps.isExpired()) { stop(); return; }
    poll();
  }, intervalMs);
  return stop;
}
