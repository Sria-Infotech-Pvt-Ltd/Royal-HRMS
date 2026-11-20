"use client";

import { useEffect } from "react";
import { isSessionKnownExpired, renewLoginIfStale } from "@/lib/clientApi";

// How often a visible tab checks whether the login is getting old. The check itself is a cheap local comparison; a refresh
// request is made only when the login is about 11 of its 15 minutes old.
const CHECK_EVERY_MS = 60_000;

/**
 * Keeps the login fresh while the app is open, so a page that has been sitting idle does not send a burst of requests with an
 * expired login and wait for each to fail first. It renews quietly: when the app opens, every minute while the tab is on screen,
 * and the moment the tab comes back into view or the network returns (the cases where the login has usually just run out).
 * The renewal goes through the same shared, locked refresh as every other refresh, so tabs never collide.
 */
export function useSessionKeepAlive(): void {
  useEffect(() => {
    function check() {
      if (document.visibilityState !== "visible" || isSessionKnownExpired()) return;
      void renewLoginIfStale();
    }
    check();
    const timer = window.setInterval(check, CHECK_EVERY_MS);
    document.addEventListener("visibilitychange", check);
    window.addEventListener("focus", check);
    window.addEventListener("online", check);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", check);
      window.removeEventListener("focus", check);
      window.removeEventListener("online", check);
    };
  }, []);
}
