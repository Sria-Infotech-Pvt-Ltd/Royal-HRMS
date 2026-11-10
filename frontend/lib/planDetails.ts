// Presentation helpers for Company Settings → Plan Details. Nothing here
// decides access: every state comes from the server (apps/tenants/customer_plan.py).

import type { ModuleAccess, ModuleSource, OtherPlan, PlanDetails, PlanModuleRow, PlanPaymentStatus } from "@/types/planDetails";

export const SOURCE_LABEL: Record<ModuleSource, string> = {
  plan:         "Included",
  dependency:   "Included",
  added:        "Added for your company",
  removed:      "Removed for your company",
  not_included: "Not included",
};

export const ACCESS_LABEL: Record<ModuleAccess, string> = {
  enabled: "Enabled",
  pending: "Activates when payment is confirmed",
  off:     "Not enabled",
};

export const PAYMENT_LABEL: Record<PlanPaymentStatus, string> = {
  pending:        "Pending",
  paid:           "Paid",
  partially_paid: "Partially paid",
  failed:         "Failed",
  waived:         "Waived",
};

/** Explanation under the "In plan" badge, e.g. "Required by Payroll". */
export function sourceNote(row: PlanModuleRow): string {
  if (row.source === "dependency" && row.required_by.length) return `Required by ${row.required_by.join(", ")}`;
  return "";
}

/** A module that is on although the subscription doesn't include it (e.g. a plan not applied yet). */
export function enabledOutsidePlan(row: PlanModuleRow, hasPlan: boolean): boolean {
  return hasPlan && row.enabled && !row.included;
}

/** Counts for the summary line above the module table. */
export function moduleSummary(rows: PlanModuleRow[]) {
  return {
    included: rows.filter(r => r.included).length,
    enabled: rows.filter(r => r.enabled).length,
    pending: rows.filter(r => r.access === "pending").length,
    notIncluded: rows.filter(r => !r.included).length,
  };
}

export interface ComparisonRow {
  key: string;
  label: string;
  current: boolean;
  plans: Record<string, boolean>;   // plan code → included
}

/** Module × (current plan, other plans) matrix; rows any plan includes, current first. */
export function comparisonRows(details: PlanDetails, plans: OtherPlan[] = details.other_plans): ComparisonRow[] {
  const current = new Set(details.modules.filter(r => r.included).map(r => r.key));
  if (!details.has_plan) details.enabled_modules.forEach(k => current.add(k));
  return details.modules
    .filter(r => current.has(r.key) || plans.some(p => p.modules.includes(r.key)))
    .map(r => ({
      key: r.key,
      label: r.label,
      current: current.has(r.key),
      plans: Object.fromEntries(plans.map(p => [p.code, p.modules.includes(r.key)])),
    }));
}

/** Labels for module keys, from the rows the server sent. */
export function moduleLabels(details: PlanDetails, keys: string[]): string[] {
  const byKey = new Map(details.modules.map(r => [r.key, r.label]));
  return keys.map(k => byKey.get(k) ?? k);
}

export function periodLabel(period: string): string {
  return period === "yearly" ? "Yearly" : period === "monthly" ? "Monthly" : "Not set";
}
