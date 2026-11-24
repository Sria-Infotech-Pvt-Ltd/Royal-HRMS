// Small pure helpers for the Separation & Exit list: which group a status belongs to, the numbers for the summary row,
// and the "last working day" countdown. Statuses are opaque backend codes (see _workflow.ts), so groups match on keywords.
import type { SeparationRequest } from "@/types/separation";
import { tr } from "@/lib/i18n/tr";
import { daysBetween, todayIso } from "./_workflow";

export type StatusGroup = "waiting" | "approved" | "closed";

export function statusGroup(status: string): StatusGroup {
  const code = status.toLowerCase();
  if (code.includes("reject") || code.includes("cancel")) return "closed";
  if (code.includes("approved") || code.includes("completed") || code.includes("cleared")) return "approved";
  return "waiting";
}

export interface SeparationCounts {
  all: number;
  waiting: number;
  approved: number;
  closed: number;
  needsMe: number;
}

export function countSeparations(rows: SeparationRequest[]): SeparationCounts {
  const counts: SeparationCounts = { all: rows.length, waiting: 0, approved: 0, closed: 0, needsMe: 0 };
  for (const row of rows) {
    counts[statusGroup(row.status)] += 1;
    if (row.can_approve) counts.needsMe += 1;
  }
  return counts;
}

export interface LastDayCountdown {
  label: string;
  tone: "soon" | "later" | "passed";
}

const SOON_WITHIN_DAYS = 14;

/** "in 12 days" / "Today" / "5 days ago" for the proposed last working day. */
export function lastDayCountdown(lastDayIso: string | null | undefined, today: string = todayIso()): LastDayCountdown | null {
  if (!lastDayIso) return null;
  const days = daysBetween(today, lastDayIso);
  if (Number.isNaN(days)) return null;
  if (days === 0) return { label: tr("Today"), tone: "soon" };
  if (days < 0) return { label: days === -1 ? tr("{count} day ago", { count: 1 }) : tr("{count} days ago", { count: -days }), tone: "passed" };
  return { label: days === 1 ? tr("in {count} day", { count: 1 }) : tr("in {count} days", { count: days }), tone: days <= SOON_WITHIN_DAYS ? "soon" : "later" };
}
