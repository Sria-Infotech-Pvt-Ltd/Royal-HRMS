// The ONE place that schedules the background download + warm-up of the face
// models. FaceModelPreloader (dashboard layout) and the clock widget both call
// scheduleFaceModelPreload() - previously each ran its own idle callback. The
// loader's shared promises already stopped the files being downloaded twice; this
// additionally stops the same work being SCHEDULED twice (and makes the delay
// one value instead of two).
//
// Preloading is deliberately NOT done on every page: callers only invoke this
// once they know the employee will be asked for a face check, so organisations
// with face verification off never pay the ~7 MB.
import { getModelLoadState, loadFaceApiModels } from "./loadModels";

// Short idle window so the dashboard's own first paint is not competing for the
// network, but a hard cap so the preload can never be postponed indefinitely.
const IDLE_TIMEOUT_MS = 1000;
const FALLBACK_DELAY_MS = 300;

interface Scheduled {
  refs: number;
  cancel: () => void;
}

let scheduled: Scheduled | null = null;

const noop = (): void => undefined;

/**
 * Schedules the preload (idle-time, once). Returns a cancel function to call from
 * an effect cleanup. Safe to call from several components: they share one timer,
 * which is only cancelled when every caller has cancelled. A no-op when the models
 * are already loading or ready, or when not running in a browser.
 */
export function scheduleFaceModelPreload(): () => void {
  if (typeof window === "undefined") return noop;
  const state = getModelLoadState();
  if (state === "loading" || state === "ready") return noop;

  if (!scheduled) {
    const run = () => {
      scheduled = null;
      // Errors are swallowed here: the clock-in flow itself retries the load, with
      // a visible error and a Try Again button, at the moment it is really needed.
      void loadFaceApiModels().catch(() => undefined);
    };
    if (typeof window.requestIdleCallback === "function") {
      const id = window.requestIdleCallback(run, { timeout: IDLE_TIMEOUT_MS });
      scheduled = { refs: 0, cancel: () => window.cancelIdleCallback(id) };
    } else {
      const id = window.setTimeout(run, FALLBACK_DELAY_MS);
      scheduled = { refs: 0, cancel: () => window.clearTimeout(id) };
    }
  }

  const entry = scheduled;
  entry.refs += 1;
  let cancelled = false;
  return () => {
    if (cancelled) return;
    cancelled = true;
    entry.refs -= 1;
    if (entry.refs <= 0 && scheduled === entry) {
      entry.cancel();
      scheduled = null;
    }
  };
}

/** Test-only. */
export function __resetPreloadForTests(): void {
  scheduled = null;
}
