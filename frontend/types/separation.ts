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

// Matches the separation activity/audit record shape from the backend
// service layer (separation_id/employee_id are implicit — the list is
// already scoped to one request — so they're omitted here). `description`
// is the fully-formatted sentence (e.g. "Test Manager approved the
// separation request." or "Ravi Kumar (HR) approved the separation
// request.") — the backend already applies the name/role display rule,
// so the frontend renders it as-is rather than reconstructing it.
export interface SeparationActivityItem {
  id:                  string;
  performed_by_id:     string;
  performed_by_name:   string;
  user_role:           string;
  action:              string | null; // not always present in the live payload
  description:         string;
  old_status:          string | null;
  old_status_display?: string | null;
  new_status:          string | null;
  new_status_display?: string | null;
  comment:             string | null;
  created_at:          string; // ISO datetime
}
