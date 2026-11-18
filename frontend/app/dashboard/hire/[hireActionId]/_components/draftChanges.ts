// The fields of a save that differ from the draft the server last reported. Sending only these (never the whole form) means a second
// open copy of the same draft, or a stale window, cannot overwrite newer typing with its own empty boxes.

const canon = (value: unknown): string => (value === undefined || value === null || value === "" ? "" : JSON.stringify(value));

/** Settings that are not part of the draft blob: always sent when asked for. */
const ALWAYS_SENT = new Set(["employment_type", "position"]);
/** Re-sent while filled so the server's duplicate-email / duplicate-mobile warning always comes back. */
const RESENT_WHEN_FILLED = new Set(["email", "phone"]);

export function changedDraftFields(payload: Record<string, unknown>, known: Record<string, unknown>): Record<string, unknown> {
  const changed: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(payload)) {
    const isAlwaysSent = ALWAYS_SENT.has(key);
    const isResent = RESENT_WHEN_FILLED.has(key) && canon(value) !== "";
    if (isAlwaysSent || isResent || canon(value) !== canon(known[key])) changed[key] = value;
  }
  return changed;
}
