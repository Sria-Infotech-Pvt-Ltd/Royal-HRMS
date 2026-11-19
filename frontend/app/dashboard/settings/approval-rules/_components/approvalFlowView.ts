// What each step of an approval flow looks like and how a rule becomes steps, kept apart so it can be tested alone.

import type { ApproverKind, GlobalApprovalRule } from "@/types/approvalMatrix";
import { tint } from "@/lib/colour";

export const BRAND = "var(--brand)";

export const WORKFLOW_ICONS: Record<string, string> = {
  leave: "ti-beach",
  expense: "ti-wallet",
  attendance_correction: "ti-clock-edit",
  timesheet: "ti-clock-check",
};

export const WORKFLOW_BLURBS: Record<string, string> = {
  leave: "Time-off requests",
  expense: "Reimbursement claims",
  attendance_correction: "Fixes to missed or wrong punches",
  timesheet: "Weekly timesheet approval",
};

export const approverIcon = (kind: ApproverKind): string => kind === "reporting_manager" ? "ti-user-star" : kind === "hr" ? "ti-users-group" : kind === "person" ? "ti-user" : "ti-user-question";

export interface FlowStep { key: "submit" | "l1" | "l2" | "done"; title: string; detail: string; icon: string; kind: ApproverKind; isMissing: boolean }

/** The steps a request goes through: submitted, level 1, level 2 (only when there is one), approved. */
export function flowSteps(l1: { kind: ApproverKind; label: string }, l2: { kind: ApproverKind; label: string }): FlowStep[] {
  const steps: FlowStep[] = [
    { key: "submit", title: "Submitted", detail: "Employee", icon: "ti-send", kind: "", isMissing: false },
    { key: "l1", title: "Level 1", detail: l1.label || "Not set", icon: approverIcon(l1.kind), kind: l1.kind, isMissing: !l1.kind },
  ];
  if (l2.kind) steps.push({ key: "l2", title: "Level 2", detail: l2.label, icon: approverIcon(l2.kind), kind: l2.kind, isMissing: false });
  steps.push({ key: "done", title: "Approved", detail: l2.kind ? "After both levels" : "After level 1", icon: "ti-circle-check", kind: "", isMissing: false });
  return steps;
}

export const flowOfRule = (rule: GlobalApprovalRule): FlowStep[] => flowSteps({ kind: rule.l1_approver_kind, label: rule.l1_approver_label }, { kind: rule.l2_approver_kind, label: rule.l2_approver_label });

/** "Asha Rao (EMP001) — Sales" -> "AR": the initials of a named person's step. */
export const initialsOf = (label: string): string => label.replace(/\(.*$/, "").split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0].toUpperCase()).join("") || "?";

export function summarise(rules: GlobalApprovalRule[]) {
  const levels = rules.flatMap(rule => [rule.l1_approver_kind, rule.l2_approver_kind]).filter(Boolean);
  return {
    workflows: rules.length,
    twoLevel: rules.filter(rule => rule.l2_approver_kind).length,
    oneLevel: rules.filter(rule => !rule.l2_approver_kind).length,
    namedPeople: levels.filter(kind => kind === "person").length,
    unset: rules.filter(rule => !rule.l1_approver_kind).length,
  };
}

export { tint };
