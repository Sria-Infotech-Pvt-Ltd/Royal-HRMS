"use client";

// ============================================================
//  Separation & Exit — frontend UI-gating only. The backend is
//  the source of truth for per-request/per-stage/per-clearance
//  actions (can_approve, can_cancel, can_edit, can_delete, and
//  each approval_stage/clearance's own can_action) — those are
//  never re-derived here. This hook only decides which broader
//  affordances to show (the employee picker, the Team Requests
//  scope), matching the "settings.edit is the universal bypass"
//  convention used throughout the HRMS.
// ============================================================

import { useAnyPermission } from "@/hooks/usePermission";

export interface SeparationAccess {
  // May select another employee when creating a request, and filter the
  // list by a specific employee_id.
  canPickEmployee: boolean;
  // May switch the list to "Team Requests" (?scope=team) — everyone else's
  // requests this viewer can act on. Still gated per-row/per-stage by the
  // backend's own can_* flags.
  canApprove:      boolean;
}

export function useSeparationAccess(): SeparationAccess {
  const canPickEmployee = useAnyPermission("employees.view", "settings.edit");
  const canApprove      = useAnyPermission("separation.approve", "settings.edit");
  return { canPickEmployee, canApprove };
}
