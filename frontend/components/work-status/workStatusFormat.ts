import type { WorkMode, WorkStatusAssignment, WorkStatusChange } from "@/types/workStatus";

/** Same labels as the server (ProjectAssignment.WORK_MODE_CHOICES). */
export const WORK_MODE_OPTIONS: { value: WorkMode; label: string }[] = [
  { value: "office",      label: "Work From Office (WFO)" },
  { value: "home",        label: "Work From Home (WFH)" },
  { value: "client_site", label: "Client Location (On-site)" },
  { value: "hybrid",      label: "Hybrid (Office + Home)" },
];

/** "Client Location (On-site) · Client HQ, Pune", or just the mode when no place is recorded. */
export function workPlaceLabel(assignment: WorkStatusAssignment): string {
  const mode = assignment.work_mode_display || assignment.work_mode;
  return assignment.work_location ? `${mode} · ${assignment.work_location}` : mode;
}

export const STATUS_BADGE: Record<string, string> = {
  active:    "badge badge-success",
  completed: "badge badge-neutral",
};

const EVENT_LABEL: Record<string, string> = {
  created:   "Assigned",
  updated:   "Updated",
  extended:  "Extended",
  ended:     "Ended early",
  completed: "Completed (end date passed)",
};

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function endLabel(assignment: WorkStatusAssignment): string {
  return fmtDate(assignment.end_date);
}

/** "Starts 1 Dec 2026", "Ends today", "Ends in 3 days", or the plain status label. */
export function statusLabel(assignment: WorkStatusAssignment): string {
  if (assignment.is_upcoming) return `Starts ${fmtDate(assignment.start_date)}`;
  if (assignment.is_ending_soon && assignment.days_left !== null) {
    if (assignment.days_left === 0) return "Ends today";
    return `Ends in ${assignment.days_left} day${assignment.days_left === 1 ? "" : "s"}`;
  }
  return assignment.assignment_status_display || assignment.assignment_status || "—";
}

export function statusBadge(assignment: WorkStatusAssignment): string {
  if (assignment.is_ending_soon) return "badge badge-warn";
  return STATUS_BADGE[assignment.assignment_status] ?? "badge badge-neutral";
}

export function changeLabel(change: WorkStatusChange | null): string {
  if (!change) return "—";
  const what = EVENT_LABEL[change.event_type] ?? change.event_type;
  const who = change.source === "system" ? "Automatic" : change.triggered_by || "Admin";
  return `${what} · ${who} · ${fmtDate(change.at)}`;
}
