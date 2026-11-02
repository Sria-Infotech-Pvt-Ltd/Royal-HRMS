import type { WorkStatusAssignment, WorkStatusChange } from "@/types/workStatus";

export const STATUS_BADGE: Record<string, string> = {
  active:    "badge badge-success",
  completed: "badge badge-neutral",
  on_hold:   "badge badge-warn",
  removed:   "badge badge-error",
};

const SOURCE_LABEL: Record<string, string> = {
  webhook:   "Pushed by Project Budgeting",
  pull:      "Pulled from Project Budgeting",
  reconcile: "Scheduled sync",
};

const EVENT_LABEL: Record<string, string> = {
  created:           "Assigned",
  updated:           "Updated",
  ended:             "Ended",
  auto_closed:       "Closed automatically (moved to a new project)",
  removed_in_source: "Removed in Project Budgeting",
  restored:          "Restored",
};

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(iso: string | null): string {
  if (!iso) return "Never";
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function endLabel(assignment: WorkStatusAssignment): string {
  return assignment.end_date ? fmtDate(assignment.end_date) : assignment.is_ongoing ? "Ongoing" : "—";
}

export function statusLabel(assignment: WorkStatusAssignment): string {
  return assignment.assignment_status_display || assignment.assignment_status || "—";
}

export function changeLabel(change: WorkStatusChange | null): string {
  if (!change) return "—";
  const what = EVENT_LABEL[change.event_type] ?? change.event_type;
  const how  = SOURCE_LABEL[change.source] ?? change.source;
  return `${what} · ${how} · ${fmtDate(change.at)}`;
}
