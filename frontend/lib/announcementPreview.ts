// Announcements page → collapsible cards. The stored body is never changed;
// the collapsed preview is only clamped visually (CSS line-clamp).

/** Lines shown while a card is collapsed. */
export const PREVIEW_LINES = 3;
/** Rough character budget of PREVIEW_LINES on a typical card width. */
const PREVIEW_CHARS = 220;

/** Whether the body is long enough that a collapsed card hides part of it (shows the expand control). */
export function isLongBody(body: string): boolean {
  const text = body.trim();
  return text.length > PREVIEW_CHARS || text.split(/\r?\n/).length > PREVIEW_LINES;
}

/** Independent per-card expand state: returns a new set with `id` toggled. */
export function toggleExpanded(expanded: ReadonlySet<number>, id: number): Set<number> {
  const next = new Set(expanded);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}
