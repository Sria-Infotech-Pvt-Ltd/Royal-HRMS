// Colours, icons, wording and date helpers for the Audit Log screen, kept apart so they can be tested alone.

import { shiftISODate } from "@/app/dashboard/attendance/_components/attendanceDates";
import { localISODate } from "@/app/dashboard/attendance/_components/monthView";

export const MODULES = [
  { value: "accounts",      label: "Accounts",      colour: "#7C3AED", icon: "ti-user-shield" },
  { value: "settings",      label: "Settings",      colour: "#7C3AED", icon: "ti-settings" },
  { value: "company",       label: "Company",       colour: "#7C3AED", icon: "ti-building" },
  { value: "branch",        label: "Company Code",  colour: "#7C3AED", icon: "ti-map-pin" },
  { value: "announcements", label: "Announcements", colour: "#7C3AED", icon: "ti-speakerphone" },
  { value: "birthday",      label: "Birthday",      colour: "#7C3AED", icon: "ti-cake" },
  { value: "timesheet",     label: "Timesheet",     colour: "#7C3AED", icon: "ti-clock" },
] as const;

const NEUTRAL = "#64748B";

export const moduleColour = (module: string): string => MODULES.find(entry => entry.value === module)?.colour ?? NEUTRAL;

/** The colour and icon for what happened: created is green, deleted red, updated orange, sign-in blue, password changes purple. */
export function actionStyle(action: string): { colour: string; icon: string } {
  if (action.endsWith("_created") || action === "create") return { colour: "#16A34A", icon: "ti-plus" };
  if (action.endsWith("_deleted") || action === "delete") return { colour: "#DC2626", icon: "ti-trash" };
  if (action.endsWith("_updated") || action === "update") return { colour: "#EA580C", icon: "ti-pencil" };
  if (action.endsWith("_activated")) return { colour: "#2563EB", icon: "ti-toggle-right" };
  if (action === "login") return { colour: "#2563EB", icon: "ti-login" };
  if (action === "logout") return { colour: NEUTRAL, icon: "ti-logout" };
  if (action.startsWith("password")) return { colour: "#7C3AED", icon: "ti-key" };
  return { colour: NEUTRAL, icon: "ti-point" };
}

export const fmtAction = (action: string): string => action.replace(/_/g, " ");

export function initialsOf(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0].toUpperCase()).join("") || "?";
}

/** "just now", "5 min ago", "3 h ago", "2 d ago"; older than a week returns null so the caller shows the date instead. */
export function relativeTime(iso: string, now: Date = new Date()): string | null {
  const minutes = Math.floor((now.getTime() - new Date(iso).getTime()) / 60_000);
  if (Number.isNaN(minutes)) return null;
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  return days < 7 ? `${days} d ago` : null;
}

export type RangeKey = "today" | "7d" | "30d" | "90d";
export const RANGES: { key: RangeKey; label: string; days: number }[] = [
  { key: "today", label: "Today", days: 0 },
  { key: "7d", label: "7 days", days: 7 },
  { key: "30d", label: "30 days", days: 30 },
  { key: "90d", label: "90 days", days: 90 },
];

/** The from and to dates (the viewer's own local days, never the UTC day) for a quick range ending today. */
export function rangeDates(key: RangeKey, todayISO: string = localISODate()): { from: string; to: string } {
  const days = RANGES.find(range => range.key === key)?.days ?? 30;
  return { from: shiftISODate(todayISO, -days), to: todayISO };
}

/** Which quick range the two dates match exactly, if any. */
export function matchingRange(from: string, to: string, todayISO: string = localISODate()): RangeKey | null {
  return RANGES.find(range => { const dates = rangeDates(range.key, todayISO); return dates.from === from && dates.to === to; })?.key ?? null;
}

export function tint(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const [red, green, blue] = [0, 2, 4].map(start => parseInt(value.slice(start, start + 2), 16));
  return `rgba(${red},${green},${blue},${alpha})`;
}
