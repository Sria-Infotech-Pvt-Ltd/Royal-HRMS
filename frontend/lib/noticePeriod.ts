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
