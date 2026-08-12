// ============================================================
//  Separation & Exit — status badge styling and small formatting
//  helpers. Separation type/reason options and the exact status
//  code enum are backend-defined (see /separation/types/ and
//  /separation/reasons/, fetched at runtime) — nothing here
//  hardcodes them. The backend already sends *_display fields on
//  every object; these helpers only cover what display fields
//  don't (badge color, date formatting, query strings).
// ============================================================

/** Best-effort badge color for an opaque backend status code — the exact
 *  status enum (pending / stage2_pending / approved / rejected / cancelled /
 *  completed / …) isn't fixed on the frontend, so this matches on keywords
 *  in the code rather than an exhaustive switch. */
export function statusBadgeClass(status: string): string {
  const s = status.toLowerCase();
  if (s.includes("reject")) return "badge-error";
  if (s.includes("cancel")) return "badge-neutral";
  if (s.includes("approved") || s.includes("completed") || s.includes("cleared")) return "badge-success";
  return "badge-warn";
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-08-10" → "Aug 10, 2026" */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

/** ISO datetime → "Aug 10, 2026, 3:45 PM" */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const datePart = `${MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
  const timePart = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return `${datePart}, ${timePart}`;
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function daysBetween(fromIso: string, toIso: string): number {
  const from = new Date(fromIso + "T00:00:00");
  const to   = new Date(toIso + "T00:00:00");
  return Math.round((to.getTime() - from.getTime()) / (1000 * 60 * 60 * 24));
}

/** Builds a query string from a params object, dropping undefined/empty
 *  values — same convention as attendance's CorrectionsTab.tsx toQuery(). */
export function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}
