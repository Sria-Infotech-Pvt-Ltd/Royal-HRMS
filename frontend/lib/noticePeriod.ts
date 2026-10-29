export type NoticeStatus = "serving" | "completed";

export function noticeRemainingLabel(daysRemaining: number | null | undefined, status: NoticeStatus | null | undefined): string {
  if (status === "completed") return "Notice completed";
  if (daysRemaining === null || daysRemaining === undefined) return "—";
  return `${daysRemaining} ${daysRemaining === 1 ? "day" : "days"} remaining`;
}

// Parses YYYY-MM-DD as a local calendar date so it never shifts a day with the viewer's timezone.
export function formatNoticeDate(value: string | null | undefined): string {
  if (!value) return "—";
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

// Employee notice period (assigned by HR in Settings → Notice Period), in
// calendar days. The expected last working day of a resignation is the
// request date + the notice period — an expectation, not the approved date.

export const MAX_NOTICE_PERIOD_DAYS = 365;

export function formatNoticePeriod(days: number | null | undefined): string {
  if (days === null || days === undefined) return "Not assigned";
  return `${days} day${days === 1 ? "" : "s"}`;
}

/** Error text for the HR input, or null when valid. Blank = clear (not assigned). */
export function noticePeriodInputError(raw: string): string | null {
  const text = raw.trim();
  if (!text) return null;
  if (!/^\d+$/.test(text)) return "Enter a whole number of days.";
  const n = Number(text);
  if (n > MAX_NOTICE_PERIOD_DAYS) return `Maximum ${MAX_NOTICE_PERIOD_DAYS} days.`;
  return null;
}

/** YYYY-MM-DD + days, in calendar days (no time-zone drift). */
export function expectedLastWorkingDay(requestDate: string, days: number | null | undefined): string | null {
  if (!requestDate || days === null || days === undefined || Number.isNaN(days)) return null;
  const [y, m, d] = requestDate.split("-").map(Number);
  if (!y || !m || !d) return null;
  const date = new Date(Date.UTC(y, m - 1, d + days));
  return date.toISOString().slice(0, 10);
}
