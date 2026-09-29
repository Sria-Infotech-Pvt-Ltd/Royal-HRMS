"use client";

import { useCallback, useEffect, useState } from "react";

// This codebase has no user-level UI-preference store to hook into (no
// Zustand, no backend field on the User model — see lib/auth.ts, which only
// persists auth state via cookies). localStorage is the closest existing
// precedent (frontend/app/dashboard/announcements/page.tsx already uses a
// raw localStorage flag for a similar per-browser, non-auth setting), so
// muting is a plain per-browser default rather than a per-account setting.
const STORAGE_KEY = "royal_hrms_voice_muted";

function readStoredPreference(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeStoredPreference(muted: boolean): void {
  if (typeof window === "undefined") return;
  try {
    if (muted) {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Storage can be unavailable (private browsing, quota) — the toggle
    // still works for the rest of this session, it just won't survive a
    // reload. Not worth surfacing an error for.
  }
}

/**
 * Whether spoken voice-command confirmations are muted, remembered across
 * reloads via localStorage. Defaults to false (unmuted) — first-time users
 * hear the confirmation; only an explicit toggle silences it.
 */
export function useVoiceMutePreference() {
  const [isMuted, setIsMuted] = useState(false);

  // Read after mount only — matches lib/auth.ts's getStoredUser() pattern of
  // guarding browser-only storage behind typeof window, and avoids an
  // SSR/hydration mismatch (server always renders the unmuted default).
  useEffect(() => {
    setIsMuted(readStoredPreference());
  }, []);

  const toggleMuted = useCallback(() => {
    setIsMuted(prev => {
      const next = !prev;
      writeStoredPreference(next);
      return next;
    });
    // Interrupting a currently-playing utterance the instant this flips true
    // is owned by useVoiceCommand (its cancelSpeech(), reacting to the
    // isMuted value this hook returns) — not here. This hook only knows the
    // preference, not the <audio> element actually playing it; a
    // window.speechSynthesis.cancel() call here was dead code left over
    // from before TTS moved to server-side Sarvam audio (BUG-001 cleanup,
    // 2026-09-23) and never actually stopped anything.
  }, []);

  return { isMuted, toggleMuted };
}
