import { tr } from "@/lib/i18n/tr";
import type { ApproverOption, ApprovalRuleSummary, PersonRef } from "@/types/approvers";

/** "Name — Role · Branch · Department", leaving out whatever is blank. */
export function optionLabel(person: Pick<ApproverOption, "full_name" | "role" | "branch" | "department">): string {
  const where = [person.branch, person.department].filter(Boolean).join(" · ");
  return [tr("{name} — {role}", { name: person.full_name, role: person.role || tr("No role set") }), where].filter(Boolean).join(" · ");
}

/** "Name — Role" for a person already chosen or named on a screen. */
export function personLine(person: PersonRef): string {
  return tr("{name} — {role}", { name: person.full_name, role: person.role || tr("No role set") });
}

/** What an empty L1 choice means. L1 is the reporting manager only if the approval rule says so; it is never assumed. */
export function l1Placeholder(rule: ApprovalRuleSummary): string {
  if (rule.l1_kind === "reporting_manager") return tr("Same as the reporting manager (approval rule)");
  return rule.l1 ? tr("Per the approval rule: {name}", { name: rule.l1 }) : tr("Per the approval rule");
}
