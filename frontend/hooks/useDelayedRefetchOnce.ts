import { useEffect, useRef } from "react";

/**
 * How long to wait before the single follow-up fetch. The server queues the Project Budgeting pull in the background;
 * on success it finishes in a second or two, and a failure gives up after the 3 s connect timeout, so by 8 s the outcome
 * is normally stored.
 */
export const SYNC_PENDING_REFETCH_DELAY_MS = 8000;

/**
 * Refetch exactly ONCE, `delayMs` after the server first reports that a background job is still running.
 *
 * Deliberately not polling: if the response to that refetch still says "pending", nothing more is scheduled (the person
 * sees the stored data and the next visit picks up the rest). Unmounting before the delay cancels it.
 *
 * `hasRefetched` marks that the refetch actually fired, not that it was scheduled. React strict mode (development) runs
 * every effect twice, cancelling the first timer; marking at schedule time would leave the second run with nothing to do and
 * no refetch would ever happen.
 */
export function useDelayedRefetchOnce(isPending: boolean, refetch: () => void, delayMs: number = SYNC_PENDING_REFETCH_DELAY_MS): void {
  const hasRefetched = useRef(false);
  // The latest refetch without restarting the timer whenever its identity changes (useFetch makes a new one per URL).
  const latestRefetch = useRef(refetch);
  useEffect(() => { latestRefetch.current = refetch; }, [refetch]);

  useEffect(() => {
    if (!isPending || hasRefetched.current) return;
    const timer = setTimeout(() => {
      hasRefetched.current = true;
      latestRefetch.current();
    }, delayMs);
    return () => clearTimeout(timer);
  }, [isPending, delayMs]);
}
