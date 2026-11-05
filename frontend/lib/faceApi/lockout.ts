// Client side of the face-verification lockout. After too many failed face
// attempts the server answers a punch with 403 and
// data: { blocked: true, retry_after_seconds }. The punch button is then
// disabled and shows "Please wait mm:ss" until that time has passed.
//
// The end time is kept in sessionStorage so the countdown survives moving
// between dashboard pages (each page mounts its own punch button). It is only a
// convenience: the server remains the authority and answers again if a punch
// is attempted early. Every storage access is wrapped - storage can be blocked.

const STORAGE_KEY = "aira_face_lockout_until";

/** Seconds -> "mm:ss" (minutes are not capped, so 15 minutes reads "15:00"). */
export function formatLockoutCountdown(totalSeconds: number): string {
  const safe = Math.max(0, Math.ceil(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/** The lockout end time (epoch ms) from a punch error's `data`, or null if it is not a lockout response. */
export function lockoutUntilFromError(data: unknown, now: number = Date.now()): number | null {
  const d = data as { blocked?: unknown; retry_after_seconds?: unknown } | null | undefined;
  if (!d || d.blocked !== true) return null;
  const seconds = d.retry_after_seconds;
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds <= 0) return null;
  return now + Math.ceil(seconds) * 1000;
}

/** Whole seconds left until `until` (epoch ms); 0 when it has passed or is unset. */
export function secondsRemaining(until: number | null, now: number = Date.now()): number {
  if (!until) return 0;
  return Math.max(0, Math.ceil((until - now) / 1000));
}

export function loadLockoutUntil(now: number = Date.now()): number | null {
  try {
    const raw = typeof window !== "undefined" ? window.sessionStorage.getItem(STORAGE_KEY) : null;
    const until = raw ? Number(raw) : NaN;
    return Number.isFinite(until) && until > now ? until : null;
  } catch {
    return null;
  }
}

export function saveLockoutUntil(until: number | null): void {
  try {
    if (typeof window === "undefined") return;
    if (until === null) window.sessionStorage.removeItem(STORAGE_KEY);
    else window.sessionStorage.setItem(STORAGE_KEY, String(until));
  } catch {
    // Storage unavailable - the countdown just won't survive a page change.
  }
}
