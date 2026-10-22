// Edit Asset → "Assignment Details": what to show for an asset's current holder.
// Only the asset API's active_assignment (the one assignment in status
// "assigned") is used — returned assignments are history and never shown here.

import type { ActiveAssignment, AssetStatus } from "@/types/assets";

export type HolderView =
  | { kind: "assigned"; employee: string; code: string | null; hidden: boolean; status: string;
      assignedDate: string; expectedReturn: string | null }
  | { kind: "none"; message: string };

export function holderView(asset: { status: AssetStatus; active_assignment?: ActiveAssignment | null }): HolderView {
  const a = asset.active_assignment;
  if (a) {
    const hidden = a.employee_hidden || !a.employee_name;
    return {
      kind: "assigned",
      employee: a.employee_hidden
        ? "Not visible to you"
        : a.employee_name || "Employee details not available",
      code: hidden ? null : a.employee_code,
      hidden,
      status: a.status_display || "Assigned",
      assignedDate: a.assigned_date,
      expectedReturn: a.expected_return_date,
    };
  }
  if (asset.status === "assigned") {
    // Status says Assigned but there is no active assignment record.
    return { kind: "none", message: "Marked Assigned, but no active assignment record was found." };
  }
  return { kind: "none", message: "Not currently assigned." };
}

export const fmtAssetDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
