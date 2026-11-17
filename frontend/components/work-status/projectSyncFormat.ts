import type { ProjectSyncLogRow } from "@/types/workStatus";

export interface SyncLogGroup {
  /** The oldest row folded into this group. */
  first:  ProjectSyncLogRow;
  /** The newest row (what the table shows). */
  latest: ProjectSyncLogRow;
  count:  number;
}

// A server that is down fails the same way every few minutes, which would bury everything else in the log. Consecutive
// identical failures (same source, employee and message) are folded into one row with a count. Rows arrive newest first.
export function groupLogs(rows: ProjectSyncLogRow[]): SyncLogGroup[] {
  const groups: SyncLogGroup[] = [];
  for (const row of rows) {
    const last = groups[groups.length - 1];
    const repeatsLast =
      last !== undefined &&
      row.status === "failed" &&
      last.latest.status === "failed" &&
      last.latest.source === row.source &&
      last.latest.employee_id === row.employee_id &&
      last.latest.message === row.message;
    if (repeatsLast) {
      last.first = row;
      last.count += 1;
    } else {
      groups.push({ first: row, latest: row, count: 1 });
    }
  }
  return groups;
}

export function whatHappened(row: ProjectSyncLogRow): string {
  const who = row.employee_id ? ` for ${row.employee_id}` : "";
  if (row.source === "webhook") return `Project Budgeting sent an update${who}`;
  if (row.source === "pull") return `Looked up${who} when their page opened`;
  return "Scheduled catch-up for all employees";
}

export function changeSummary(row: ProjectSyncLogRow): string {
  if (row.status === "failed") return "";
  const parts = [
    row.saved   ? `${row.saved} saved`     : "",
    row.changed ? `${row.changed} changed` : "",
    row.removed ? `${row.removed} removed` : "",
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "No changes";
}
