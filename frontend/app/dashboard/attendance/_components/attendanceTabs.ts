// The Attendance page's tab and Team/Employee view live in the URL (?tab=...&view=...), so a refresh, a shared link and the
// browser's back/forward buttons all land on the same screen instead of silently falling back to the first tab.

export const ATTENDANCE_TAB_IDS = ["attendance", "ot", "invalid", "unpunches", "corrections", "weekly-off"] as const;
export type AttendanceTabId = (typeof ATTENDANCE_TAB_IDS)[number];
export type AttendanceViewMode = "team" | "employee";

export interface AttendanceLocation {
  tab: AttendanceTabId;
  view: AttendanceViewMode;
}

const DEFAULT_LOCATION: AttendanceLocation = { tab: "attendance", view: "team" };

function isTabId(value: string | null): value is AttendanceTabId {
  return ATTENDANCE_TAB_IDS.some(id => id === value);
}

/** Reads the tab/view from a query string; anything missing or unknown falls back to Attendance > Team Day View. */
export function parseAttendanceLocation(search: string): AttendanceLocation {
  const params = new URLSearchParams(search);
  const tab = params.get("tab");
  return {
    tab: isTabId(tab) ? tab : DEFAULT_LOCATION.tab,
    view: params.get("view") === "employee" ? "employee" : DEFAULT_LOCATION.view,
  };
}

/** The query string for a location, keeping unrelated params (employee, month, ...) and dropping the defaults. */
export function buildAttendanceSearch(existing: string, location: AttendanceLocation): string {
  const params = new URLSearchParams(existing);
  if (location.tab === DEFAULT_LOCATION.tab) params.delete("tab"); else params.set("tab", location.tab);
  // The view only means something on the Attendance tab.
  if (location.tab === "attendance" && location.view === "employee") params.set("view", "employee"); else params.delete("view");
  const text = params.toString();
  return text ? `?${text}` : "";
}
