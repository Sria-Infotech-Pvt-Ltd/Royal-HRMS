import { tint } from "@/lib/colour";
// Types, colours and small helpers for the Leave Types screen, kept apart from the screens so they can be tested alone.

export interface LeavePolicy {
  id: number;
  leave_type: string;
  leave_type_display: string;
  annual_days: number;
  accrual_frequency: "annual" | "monthly";
  can_carry_forward: boolean;
  max_carry_forward_days: number;
  policy_note: string;
  is_active: boolean;
  updated_at: string;
}

// Built-in leave types can be deactivated but never deleted: mirrors the _BUILTIN set enforced server-side in LeavePolicyView.delete().
export const BUILTIN_TYPES = new Set(["casual", "earned", "sick", "lwp", "maternity", "paternity"]);

const TYPE_COLOURS: Record<string, string> = {
  casual: "#7C3AED", earned: "#16A34A", sick: "#EA580C", lwp: "#64748B", maternity: "#DB2777", paternity: "#2563EB",
  bereavement: "#475569", comp_off: "#0891B2",
};
const FALLBACK_COLOURS = ["#0891B2", "#9333EA", "#CA8A04", "#0D9488", "#E11D48", "#4F46E5"];

const TYPE_ICONS: Record<string, string> = {
  casual: "ti-beach", earned: "ti-medal", sick: "ti-stethoscope", lwp: "ti-currency-rupee-off", maternity: "ti-baby-carriage",
  paternity: "ti-mood-kid", bereavement: "ti-heart-broken", comp_off: "ti-clock-plus",
};

/** A steady colour for a leave type: the known ones keep theirs, a new one gets a colour from its key, always the same one. */
export function leaveTypeColour(key: string): string {
  if (TYPE_COLOURS[key]) return TYPE_COLOURS[key];
  let sum = 0;
  for (const char of key) sum += char.charCodeAt(0);
  return FALLBACK_COLOURS[sum % FALLBACK_COLOURS.length];
}

export const leaveTypeIcon = (key: string): string => TYPE_ICONS[key] ?? "ti-calendar-event";

export { tint };

export type StatusFilter = "all" | "active" | "inactive";

/** The leave types matching the typed words (in the name or the note) and the chosen status. */
export function filterLeaveTypes(list: LeavePolicy[], search: string, status: StatusFilter): LeavePolicy[] {
  const words = search.toLowerCase().split(/\s+/).filter(Boolean);
  return list.filter(policy => {
    if (status === "active" && !policy.is_active) return false;
    if (status === "inactive" && policy.is_active) return false;
    const text = `${policy.leave_type_display} ${policy.policy_note ?? ""}`.toLowerCase();
    return words.every(word => text.includes(word));
  });
}

export function summarise(list: LeavePolicy[]) {
  return {
    total: list.length,
    active: list.filter(policy => policy.is_active).length,
    carryForward: list.filter(policy => policy.can_carry_forward).length,
    annualDays: list.filter(policy => policy.is_active).reduce((sum, policy) => sum + Number(policy.annual_days), 0),
  };
}
