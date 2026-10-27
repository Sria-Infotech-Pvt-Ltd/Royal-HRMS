// My Profile → Work Info: display text for an assigned person (Reporting
// Manager, Reporting Approver, HR) from /employees/me/, which returns
// { id, name } or null. Only the name is ever shown — never a raw id.

export interface AssignedPersonLike {
  id?: string | null;
  name?: string | null;
}

export const NOT_ASSIGNED = "Not assigned";

export function assignedName(person: AssignedPersonLike | null | undefined): string {
  const name = person?.name?.trim();
  return name ? name : NOT_ASSIGNED;
}
