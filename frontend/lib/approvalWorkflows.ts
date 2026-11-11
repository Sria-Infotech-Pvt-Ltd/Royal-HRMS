// Phase 3 approval workflows — pure helpers shared by the escalation settings
// card, the delegation section and the leave cancellation panels.
// The backend re-validates everything; these only give instant feedback.

export interface PersonRef {
  id: string;
  name: string;
  employee_id: string;
  branch: string;
}

export interface EscalationSettings {
  is_enabled: boolean;
  reminder_after_days: number;
  first_escalation_after_days: number;
  second_escalation_after_days: number;
  escalation_head: PersonRef | null;
  applies_to_leave: boolean;
  applies_to_attendance: boolean;
  can_edit?: boolean;
}

export type EscalationForm = Omit<EscalationSettings, "escalation_head" | "can_edit"> & {
  escalation_head: string; // user id, "" = none
};

export type Workflow = "leave" | "attendance";

export interface Delegation {
  id: string;
  delegator: PersonRef;
  delegate: PersonRef;
  start_date: string;
  end_date: string;
  workflows: Workflow[];
  reason: string;
  active: boolean;
  revoked: boolean;
  revoked_at: string | null;
  can_revoke: boolean;
  given: boolean;     // I am the approver who delegated
  received: boolean;  // I am the delegate
  created_at: string;
}

export interface DelegationForm {
  delegate: string;
  start_date: string;
  end_date: string;
  workflows: Workflow[];
  reason: string;
}

export const MAX_DELEGATION_DAYS = 180;
export const WORKFLOW_LABEL: Record<Workflow, string> = { leave: "Leave", attendance: "Attendance" };

export function toEscalationForm(s: EscalationSettings): EscalationForm {
  return {
    is_enabled: s.is_enabled,
    reminder_after_days: s.reminder_after_days,
    first_escalation_after_days: s.first_escalation_after_days,
    second_escalation_after_days: s.second_escalation_after_days,
    escalation_head: s.escalation_head?.id ?? "",
    applies_to_leave: s.applies_to_leave,
    applies_to_attendance: s.applies_to_attendance,
  };
}

function whole(n: number, min: number, max: number): boolean {
  return Number.isInteger(n) && n >= min && n <= max;
}

/** Field → message; empty when valid. Mirrors the backend serializer. */
export function validateEscalation(f: EscalationForm): Record<string, string> {
  const e: Record<string, string> = {};
  if (!whole(f.reminder_after_days, 0, 30)) e.reminder_after_days = "Enter 0–30 working days (0 = no reminder).";
  if (!whole(f.first_escalation_after_days, 1, 30)) e.first_escalation_after_days = "Enter 1–30 working days.";
  if (!whole(f.second_escalation_after_days, 0, 30))
    e.second_escalation_after_days = "Enter 0–30 working days (0 = no second escalation).";
  if (!e.reminder_after_days && !e.first_escalation_after_days && f.reminder_after_days > 0
      && f.reminder_after_days >= f.first_escalation_after_days)
    e.reminder_after_days = "The reminder must come before the first escalation.";
  if (f.is_enabled && !f.applies_to_leave && !f.applies_to_attendance)
    e.applies_to_leave = "Choose at least one request type.";
  return e;
}

export interface TimelineStep {
  day: number;
  text: string;
}

/** Human-readable timeline of what happens to a request waiting at one stage. */
export function escalationTimeline(f: EscalationForm, headName = ""): TimelineStep[] {
  const steps: TimelineStep[] = [];
  if (f.reminder_after_days > 0)
    steps.push({ day: f.reminder_after_days, text: "Reminder to the current approver (and their delegate)" });
  steps.push({ day: f.first_escalation_after_days, text: "Escalated to the approver's reporting manager (next higher approver)" });
  if (f.second_escalation_after_days > 0) {
    steps.push({
      day: f.first_escalation_after_days + f.second_escalation_after_days,
      text: headName ? `Escalated to ${headName} (escalation head)` : "Escalation head not set — this step is skipped",
    });
  }
  return steps;
}

export function daysBetweenInclusive(start: string, end: string): number {
  const a = Date.parse(`${start}T00:00:00Z`);
  const b = Date.parse(`${end}T00:00:00Z`);
  return Math.round((b - a) / 86_400_000) + 1;
}

export function validateDelegation(f: DelegationForm, today: string): Record<string, string> {
  const e: Record<string, string> = {};
  if (!f.delegate) e.delegate = "Choose who approves in your place.";
  if (!f.workflows.length) e.workflows = "Choose Leave and/or Attendance requests.";
  if (!f.start_date) e.start_date = "Choose a start date.";
  if (!f.end_date) e.end_date = "Choose an end date.";
  if (f.start_date && f.end_date) {
    if (f.end_date < f.start_date) e.end_date = "The end date must be on or after the start date.";
    else if (f.end_date < today) e.end_date = "The end date is in the past.";
    else if (daysBetweenInclusive(f.start_date, f.end_date) > MAX_DELEGATION_DAYS)
      e.end_date = `A delegation can last at most ${MAX_DELEGATION_DAYS} days.`;
  }
  if (f.reason.length > 300) e.reason = "Keep the reason under 300 characters.";
  return e;
}

export type DelegationState = "active" | "scheduled" | "ended" | "revoked";

export function delegationState(d: Pick<Delegation, "revoked" | "start_date" | "end_date">, today: string): DelegationState {
  if (d.revoked) return "revoked";
  if (d.end_date < today) return "ended";
  if (d.start_date > today) return "scheduled";
  return "active";
}

export const DELEGATION_STATE_LABEL: Record<DelegationState, string> = {
  active: "Active", scheduled: "Scheduled", ended: "Ended", revoked: "Revoked",
};

export const DELEGATION_STATE_BADGE: Record<DelegationState, string> = {
  active: "badge-success", scheduled: "badge-info", ended: "badge-neutral", revoked: "badge-error",
};

export type CancellationStatus = "" | "requested" | "approved" | "rejected";

export function cancellationBadge(status: CancellationStatus | undefined | null): { label: string; cls: string } | null {
  switch (status) {
    case "requested": return { label: "Cancellation pending", cls: "badge-warn" };
    case "approved":  return { label: "Cancellation approved", cls: "badge-success" };
    case "rejected":  return { label: "Cancellation rejected", cls: "badge-error" };
    default:          return null;
  }
}

/** Message for an invalid cancellation reason / rejection remark, or "" when OK. */
export function cancellationReasonError(reason: string): string {
  return reason.trim().length < 5 ? "Give a reason (at least 5 characters)." : "";
}

export function rejectRemarksError(remarks: string): string {
  return remarks.trim() ? "" : "Give a reason for rejecting — it is shown to the employee.";
}

export function localToday(now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function apiMessage(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: { message?: string } } })?.response?.data;
  return data?.message || fallback;
}
