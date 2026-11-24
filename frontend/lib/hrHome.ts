// Pure helpers behind the HR dashboard (/dashboard/hr): every number shown there is derived here from the counts the
// existing workflow APIs return, so nothing on the screen is typed in by hand. A count that has no data source is
// represented as null and shown as a dash.
import { tr } from "@/lib/i18n/tr";
import type { KindCount } from "@/lib/approvalOverview";

export interface PendingRequestRow {
  key: string;
  label: string;
  sub: string;
  count: number;
}

interface PendingInput {
  /** Per-workflow counts, or null when the viewer cannot approve those workflows. */
  team: KindCount[] | null;
  /** Face ID registrations waiting in the viewer's queue, or null when the viewer cannot approve them. */
  face: number | null;
}

const hasKind = (team: KindCount[], kind: KindCount["kind"]) => team.some(count => count.kind === kind);
const pendingOf = (team: KindCount[], kind: KindCount["kind"]) => team.find(count => count.kind === kind)?.pending ?? 0;

/**
 * The rows of "My Pending Requests", in the order the design shows them. A workflow the viewer cannot approve has no row
 * (its kind is absent from `team`), so it is never shown as a misleading zero.
 */
export function pendingRequestRows({ team, face }: PendingInput): PendingRequestRow[] {
  const rows: PendingRequestRow[] = [];
  const kinds = team ?? [];
  if (face !== null) rows.push({ key: "face", label: tr("Face Registration"), sub: tr("Employees awaiting approval"), count: face });
  if (hasKind(kinds, "leave")) rows.push({ key: "leave", label: tr("Leave Requests"), sub: tr("L1/L2 approvals pending"), count: pendingOf(kinds, "leave") });
  if (hasKind(kinds, "wfh")) rows.push({ key: "wfh", label: tr("Work From Home"), sub: tr("WFH requests for approval"), count: pendingOf(kinds, "wfh") });
  if (hasKind(kinds, "expense")) rows.push({ key: "expense", label: tr("Expense Requests"), sub: tr("Claims awaiting review"), count: pendingOf(kinds, "expense") });
  if (hasKind(kinds, "attendance_correction") || hasKind(kinds, "separation")) {
    rows.push({
      key: "other", label: tr("Other Requests"), sub: tr("Regularization, separation"),
      count: pendingOf(kinds, "attendance_correction") + pendingOf(kinds, "separation"),
    });
  }
  return rows;
}

export function totalPending(rows: PendingRequestRow[]): number {
  return rows.reduce((sum, row) => sum + row.count, 0);
}

/** Requests that need this person's own decision right now (the server's per-row "can act" answer), plus the Face ID queue. */
export function pendingApprovalsForMe({ team, face }: PendingInput): number {
  return (team ?? []).reduce((sum, count) => sum + count.needsMyAction, 0) + (face ?? 0);
}

export function greetingFor(hour: number): string {
  return hour < 12 ? tr("Good morning") : hour < 17 ? tr("Good afternoon") : tr("Good evening");
}

export function initialsOf(name: string): string {
  return name.split(/\s+/).filter(Boolean).map(part => part[0]).join("").toUpperCase().slice(0, 2) || "?";
}

/** "10 minutes ago", "1 hour ago", "2 days ago". `now` is passed in so the result is testable. */
export function relativeTime(iso: string, now: Date): string {
  const minutes = Math.max(0, Math.floor((now.getTime() - new Date(iso).getTime()) / 60000));
  if (minutes < 1) return tr("just now");
  if (minutes < 60) return (minutes === 1 ? tr("{count} minute ago", { count: minutes }) : tr("{count} minutes ago", { count: minutes }));
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return (hours === 1 ? tr("{count} hour ago", { count: hours }) : tr("{count} hours ago", { count: hours }));
  const days = Math.floor(hours / 24);
  return (days === 1 ? tr("{count} day ago", { count: days }) : tr("{count} days ago", { count: days }));
}

/** A count for display: a real number, or a dash when the source has no value (never a made-up figure). */
export function countOrDash(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : String(value);
}
