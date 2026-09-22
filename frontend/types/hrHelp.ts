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
}

// Topic value backing "Document request" (e.g. the employment letter request
// submitted via my-requests/_components/EmployeeRequestModal.tsx) — the one
// topic where a resolved request represents a deliverable actually handed
// back to the employee, not just a closed conversation. Kept here as the
// single source of truth rather than a repeated string literal.
export const HR_HELP_DOCUMENT_TOPIC = "document_request";
