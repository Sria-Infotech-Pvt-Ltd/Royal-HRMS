"use client";

import { useCallback, useEffect, useState } from "react";
import { lockoutUntilFromError, saveLockoutUntil, secondsRemaining } from "@/lib/faceApi/lockout";
import { activeLockoutSeconds } from "@/lib/voiceLockout";

/**
 * Voice side of the shared face-verification lockout.
 *
 * Reuses lib/faceApi/lockout.ts and its sessionStorage key, so a lockout recorded by the manual Punch In/Out button
 * and one recorded by a voice punch are the same lockout. It is a convenience only: the server answers again (with a
 * fresh countdown) whenever a punch is attempted early, and stays the authority.
 *
 * Ticks once per second, re-reading storage so a lockout started elsewhere in the same tab also appears; state only
 * changes (and the host re-renders) when the whole-second value changes, so an idle hook costs nothing.
 */
export function useVoiceLockout() {
  const [lockoutSecondsRemaining, setLockoutSecondsRemaining] = useState(0);

  useEffect(() => {
    const sync = () => setLockoutSecondsRemaining(activeLockoutSeconds());
    sync();
    const timer = setInterval(sync, 1000);
    return () => clearInterval(timer);
  }, []);

  /** Records a lockout from a voice response's `result` ({ blocked, retry_after_seconds }); false if it is not one. */
  const recordLockout = useCallback((result: unknown): boolean => {
    const until = lockoutUntilFromError(result);
    if (until === null) return false;
    saveLockoutUntil(until);
    setLockoutSecondsRemaining(secondsRemaining(until));
    return true;
  }, []);

  return { lockoutSecondsRemaining, isLockedOut: lockoutSecondsRemaining > 0, recordLockout };
}
