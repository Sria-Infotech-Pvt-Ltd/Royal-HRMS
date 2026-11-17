import type { ApprovalRulePerson, ApproverKind } from "@/types/approvalMatrix";

/** What an L1 / L2 dropdown can hold: a relationship ("Reporting manager", "HR partner") or one named person. */
export interface ApproverChoice { kind: ApproverKind; userId: string | null }

export interface ApproverOption { value: string; label: string }

const PERSON_PREFIX = "person:";

const RELATIONSHIP_OPTIONS: ApproverOption[] = [
  { value: "reporting_manager", label: "Reporting manager" },
  { value: "hr",                label: "HR partner" },
];

function personLabel(person: ApprovalRulePerson): string {
  const unit = person.department ? ` — ${person.department}` : "";
  return `${person.full_name} (${person.employee_id})${unit}`;
}

/** The dropdown's value for a rule's saved choice: "reporting_manager", "hr", "person:<id>", or "" for none. */
export function toSelectValue(kind: ApproverKind, userId: string | null): string {
  return kind === "person" && userId ? `${PERSON_PREFIX}${userId}` : kind === "person" ? "" : kind;
}

/** The inverse of toSelectValue: what to send to the server for a dropdown value. */
export function fromSelectValue(value: string): ApproverChoice {
  if (value.startsWith(PERSON_PREFIX)) return { kind: "person", userId: value.slice(PERSON_PREFIX.length) };
  return { kind: value === "reporting_manager" || value === "hr" ? value : "", userId: null };
}

/**
 * Options for one dropdown: the two relationships, then every person who may approve this workflow. A person already saved on
 * the rule is kept in the list even if they have since stopped being eligible, so the box never shows blank for a saved choice.
 */
export function buildApproverOptions(
  eligible: ApprovalRulePerson[],
  saved: { userId: string | null; label: string } | null = null,
): ApproverOption[] {
  const people = eligible.map(person => ({ value: `${PERSON_PREFIX}${person.id}`, label: personLabel(person) }));
  const isSavedMissing = saved?.userId && !eligible.some(person => person.id === saved.userId);
  if (saved?.userId && isSavedMissing) people.unshift({ value: `${PERSON_PREFIX}${saved.userId}`, label: `${saved.label} (no longer eligible)` });
  return [...RELATIONSHIP_OPTIONS, ...people];
}
