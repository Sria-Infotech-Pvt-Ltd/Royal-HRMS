// ============================================================
//  Separation & Exit — shared types, matching the real backend
//  contract at /api/separation/requests/. Status codes and the
//  separation type/reason enums are backend-defined and fetched
//  at runtime (see /separation/types/ and /separation/reasons/)
//  rather than hardcoded — the *_display fields and the can_*
//  flags are computed server-side and must never be re-derived.
// ============================================================

export interface AssignedPerson {
  id:   string;
  name: string;
}

export interface SeparationLookupOption {
  value: string;
  label: string;
}

// Only present on /separation/types/ entries (not /separation/reasons/) —
// tells the request form which fields actually apply once this type is
// picked, e.g. Retirement has no "reason" and Absconding has no notice
// period. See backend SEPARATION_REASON_APPLICABLE_TYPES's own comment.
export interface SeparationTypeOption extends SeparationLookupOption {
  reason_applicable: boolean;
  notice_period_applicable: boolean;
}

export interface ApprovalStage {
  id:             string;
  stage:          string;
  stage_display:  string;
  sequence:       number;
  status:         string;
  status_display: string;
  approver_name:  string;
  remarks:        string;
  actioned_at:    string | null;
  can_action:     boolean;
}

export interface SeparationRequest {
  id:                         string;
  request_ref:                string;
  separation_type:            string;
  separation_type_display:    string;
  reason:                     string;
  reason_display:             string;
  reason_note:                string;
  request_date:               string; // ISO date
  proposed_last_working_day:  string; // ISO date
  notice_period_days:         number;
  comments:                   string;
  status:                     string;
  status_display:             string;
  employee_name:              string;
  employee_code:              string;
  employee_department:        string;
  employee_designation:       string;
  reporting_manager:          AssignedPerson | null;
  document_url:               string | null;
  created_by_name:            string;
  approval_stages:            ApprovalStage[];
  can_approve:                boolean;
  can_cancel:                 boolean;
  can_edit:                   boolean;
  can_delete:                 boolean;
  is_own:                     boolean; // true when the viewer is the employee this request is for
  created_at:                 string; // ISO datetime
}

export interface PaginatedResponse<T> {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     T[];
}

export type SeparationScope = "team";

export interface SeparationListParams {
  page?:            number;
  page_size?:       number;
  status?:          string;
  separation_type?: string;
  scope?:           SeparationScope | "";
  employee_id?:     string;
}

export interface KtHandoverTask {
  id:               string;
  task:             string;
  description:      string;
  assigned_to:      string | null; // User UUID
  assigned_to_name: string;
  due_date:         string | null; // ISO date
  is_completed:     boolean;
  completed_at:     string | null; // ISO datetime
  created_by_name:  string;
  created_at:       string; // ISO datetime
}

// Full & Final settlement for one separation request. pro_rata_salary
// through notice_period_recovery_amount are system-computed (see backend
// services_settlement.compute_draft() for the exact formula and its
// documented simplifications) — everything from gratuity_amount onward is
// always HR/Finance-entered by hand, matching real-world practice.
export interface SettlementItem {
  id:                            string;
  pro_rata_salary:               string;
  leave_encashment_days:         string;
  leave_encashment_amount:       string;
  notice_period_required_days:   number;
  notice_period_served_days:     number;
  notice_period_shortfall_days:  number;
  notice_period_recovery_amount: string;
  gratuity_amount:               string;
  statutory_bonus_amount:        string;
  reimbursements_amount:         string;
  advances_recovery_amount:      string;
  tds_amount:                    string;
  other_adjustment_amount:       string;
  other_adjustment_note:         string;
  net_payable_amount:            string;
  status:                        "draft" | "finalized";
  status_display:                string;
  finalized_by_name:             string;
  finalized_at:                  string | null;
  can_edit:                      boolean;
  can_finalize:                  boolean;
  created_at:                    string;
  updated_at:                    string;
}

export interface ClearanceItem {
  id:                     string;
  clearance_type:         string;
  clearance_type_display: string;
  status:                 string;
  status_display:         string;
  cleared_by_name:        string;
  remarks:                string;
  actioned_at:            string | null;
  can_action:             boolean;
}

// Not fully specified by the backend team yet — kept loose with fallbacks so
// the UI degrades gracefully instead of crashing if a field name differs.
export interface SeparationDocumentItem {
  id:               string;
  name?:            string;
  file_name?:       string;
  document_url?:    string;
  url?:             string;
  uploaded_by_name?: string;
  uploaded_at?:     string;
  created_at?:      string;
}

// Matches SeparationActivitySerializer. `message` is the fully-formatted
// sentence (e.g. "Manager Approval approved by Ravi Kumar.") — the backend
// already builds it, so the frontend renders it as-is. `actor_role` is the
// actor's Role.name ("employee" / "manager" / "hr_admin" / "system_admin" /
// "branch_admin"), or "system" when no actor is attached — it drives the
// Employee / Manager / HR grouping on the profile page.
export interface SeparationActivityItem {
  id:         string;
  message:    string;
  actor_name: string;
  actor_role: string;
  created_at: string; // ISO datetime
}
