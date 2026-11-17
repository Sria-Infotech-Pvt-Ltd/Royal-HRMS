import type { ProjectSyncLogRow } from "@/types/workStatus";

export interface SyncLogGroup {
  /** The oldest row folded into this group. */
  first:  ProjectSyncLogRow;
  /** The newest row (what the table shows). */
  latest: ProjectSyncLogRow;
  count:  number;
}

// A server that is down fails the same way every few minutes, which would bury everything else in the log. Consecutive
// identical failures (same source, employee and plain message) are folded into one row with a count. Rows arrive newest first.
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
      plainMessage(last.latest.message) === plainMessage(row.message);
    if (repeatsLast) {
      last.first = row;
      last.count += 1;
    } else {
      groups.push({ first: row, latest: row, count: 1 });
    }
  }
  return groups;
}

// Rows written before the backend started storing plain sentences hold the raw connection error (class names, memory
// addresses, the whole URL). Show those as the same sentence the backend now writes; anything else is shown as stored.
export function plainMessage(message: string): string {
  if (!message) return "";
  if (/ConnectTimeout|timed out/i.test(message)) return "Project Budgeting did not answer (connection timed out). Is it running and reachable?";
  if (/NewConnectionError|ConnectionRefused|Connection refused|Failed to establish/i.test(message)) return "Could not connect to Project Budgeting. Is it running and reachable?";
  if (/ReadTimeout|Read timed out/i.test(message)) return "Project Budgeting took too long to reply.";
  if (/HTTPConnectionPool|HTTPSConnectionPool|MaxRetryError/.test(message)) return "Could not reach Project Budgeting.";
  return message;
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
