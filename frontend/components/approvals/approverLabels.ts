import type { ApproverOption, ApprovalRuleSummary, PersonRef } from "@/types/approvers";

/** "Name — Role · Branch · Department", leaving out whatever is blank. */
export function optionLabel(person: Pick<ApproverOption, "full_name" | "role" | "branch" | "department">): string {
  const where = [person.branch, person.department].filter(Boolean).join(" · ");
  return [`${person.full_name} — ${person.role || "No role set"}`, where].filter(Boolean).join(" · ");
}

/** "Name — Role" for a person already chosen or named on a screen. */
export function personLine(person: PersonRef): string {
  return `${person.full_name} — ${person.role || "No role set"}`;
}

/** What an empty L1 choice means. L1 is the reporting manager only if the approval rule says so; it is never assumed. */
export function l1Placeholder(rule: ApprovalRuleSummary): string {
  if (rule.l1_kind === "reporting_manager") return "Same as the reporting manager (approval rule)";
  return rule.l1 ? `Per the approval rule: ${rule.l1}` : "Per the approval rule";
}
