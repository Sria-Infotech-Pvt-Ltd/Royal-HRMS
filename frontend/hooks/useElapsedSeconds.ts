"use client";

import { useEffect, useState } from "react";

// A running clock must come from the real time, not from counting ticks: browsers slow timers right down in a hidden or minimised tab
// (and stop them while the computer sleeps), so a counter that adds 1 per tick falls behind and stays behind. These hooks measure how
// much real time has passed since the server's figure arrived, so a missed tick changes nothing.

const REFRESH_EVERY_MS = 5 * 60 * 1000;

interface SyncPoint {
  token: unknown;
  at: number;
}

/**
 * Whole seconds of real time since `syncToken` last changed (the moment fresh server figures arrived), while `isRunning`.
 * It re-reads the clock every second and the instant the tab becomes visible or focused again, so it is right even when the
 * browser skipped ticks in the meantime. Add it to the server's seconds to show the live figure.
 */
export function useElapsedSeconds(syncToken: unknown, isRunning: boolean): number {
  const [sync, setSync] = useState<SyncPoint | null>(null);
  const [nowMs, setNowMs] = useState(0);

  // New server figures: restart the measurement from now. Until this effect has run, the old origin does not match the token and
  // nothing is added, so there is no frame that shows new figures plus the old elapsed time.
  useEffect(() => {
    const now = Date.now();
    setSync({ token: syncToken, at: now });
    setNowMs(now);
  }, [syncToken]);

  useEffect(() => {
    if (!isRunning) return;
    const refresh = () => setNowMs(Date.now());
    const id = setInterval(refresh, 1000);
    function refreshWhenVisible() {
      if (document.visibilityState === "visible") refresh();
    }
    document.addEventListener("visibilitychange", refreshWhenVisible);
    window.addEventListener("focus", refresh);
    window.addEventListener("pageshow", refresh);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("pageshow", refresh);
    };
  }, [isRunning]);

  if (!isRunning || !sync || sync.token !== syncToken) return 0;
  return Math.max(0, Math.floor((nowMs - sync.at) / 1000));
}

/**
 * Asks `refetch` for fresh server figures when the tab becomes visible again, and every few minutes while `isActive`, so a figure that
 * has gone stale (or a punch made on another device) is corrected without a reload.
 */
export function useRefetchWhileActive(refetch: () => void, isActive: boolean): void {
  useEffect(() => {
    if (!isActive) return;
    const id = setInterval(refetch, REFRESH_EVERY_MS);
    function refetchWhenVisible() {
      if (document.visibilityState === "visible") refetch();
    }
    document.addEventListener("visibilitychange", refetchWhenVisible);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", refetchWhenVisible);
    };
  }, [refetch, isActive]);
}
