import { formatLockoutCountdown, loadLockoutUntil, secondsRemaining } from "@/lib/faceApi/lockout";

/** The one line shown (and spoken) while a face lockout is active. */
export function voiceLockoutNotice(seconds: number): string {
  return `Face check locked. Try again in ${formatLockoutCountdown(seconds)}`;
}

/**
 * Whole seconds left on the shared face lockout right now (0 when none). Reads storage fresh on every call, so a
 * lockout recorded by the manual Punch In/Out button in this tab is seen too. The server stays the authority.
 */
export function activeLockoutSeconds(now: number = Date.now()): number {
  return secondsRemaining(loadLockoutUntil(now), now);
}
