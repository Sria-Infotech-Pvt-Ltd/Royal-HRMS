/** Deep link to one announcement: the Announcements page opens it in its detail view. Used by the notification bell and the
    dashboard card, so clicking "New Announcement" lands on that announcement and not just the list. */
export const ANNOUNCEMENTS_PATH = "/dashboard/announcements";
export const ANNOUNCEMENT_OPEN_PARAM = "open";

/** The link that opens announcement `id`. */
export function announcementLinkHref(id: number | string): string {
  return `${ANNOUNCEMENTS_PATH}?${ANNOUNCEMENT_OPEN_PARAM}=${encodeURIComponent(String(id))}`;
}

/** The announcement id a link asks for, or null when the value is missing or not a plain positive whole number. */
export function parseLinkedAnnouncementId(value: string | null | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}
