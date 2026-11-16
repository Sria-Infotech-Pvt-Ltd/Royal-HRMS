// Field names mirror HRHelpRequestSerializer (backend/apps/hrms/serializers.py)
// — same raw-API-shape convention as types/workFromHome.ts / types/orgChart.ts.
export interface HrHelpRequest {
  id:                 string;
  request_ref:        string;
  topic:              string;
  topic_display:      string;
  priority:           string;
  priority_display:   string;
  message:            string;
  status:             "open" | "in_progress" | "resolved";
  status_display:     string;
  response:           string;
  submitted_by_name:  string;
  assigned_to_name:   string;
  created_at:         string;
  updated_at:         string;
  resolved_at:        string | null;
  /** Employee id (e.g. 10000001) of whoever raised it, to open their record. */
  submitted_by_code:  string;
  /** Set on a profile correction that carries a new value HR can apply in one step; '' for every other ticket. */
  change_field:       string;
  change_label:       string;
  change_old_value:   string;
  change_new_value:   string;
  /** '' until decided, then 'applied' or 'rejected'. */
  change_decision:    "" | "applied" | "rejected";
  change_applied_at:  string | null;
  /** The joining date: only a System Admin may apply it. */
  change_needs_system_admin: boolean;
  /** An older, still open profile correction without a stored value: the field it is about, so HR can type the new value. */
  change_suggested_key: string;
}

/** One profile field an employee can ask to change with a new value (GET /hr-help/change-fields/). */
export interface ProfileChangeField {
  key:        string;
  section:    string;
  label:      string;
  kind:       "text" | "date" | "phone" | "pin" | "choice";
  max_length: number;
  choices:    { value: string; label: string }[];
  full_access_only: boolean;
}

// Topic value backing "Document request" (e.g. the employment letter request
// submitted via my-requests/_components/EmployeeRequestModal.tsx) — the one
// topic where a resolved request represents a deliverable actually handed
// back to the employee, not just a closed conversation. Kept here as the
// single source of truth rather than a repeated string literal.
export const HR_HELP_DOCUMENT_TOPIC = "document_request";
