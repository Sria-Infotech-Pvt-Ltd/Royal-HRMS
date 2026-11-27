// Work Status: project assignments that admins create and manage in AIRA HRMS (assign, edit, extend, end).

export type AssignmentStatus = "active" | "completed";

export type AssignmentAction = "assign" | "edit" | "extend" | "end";

/** Where the employee works on the project; labels are in components/work-status/workStatusFormat.ts (WORK_MODE_OPTIONS). */
export type WorkMode = "office" | "home" | "client_site" | "hybrid";

/** What the assign / edit / extend / end dialog sends; each action uses the fields it needs. */
export interface AssignmentForm {
  project_name: string;
  start_date:   string;
  end_date:     string;
  role:         string;
  work_mode:    WorkMode;
  /** The client's address or site (required for client_site), or the office/branch. */
  work_location: string;
  notes:        string;
  reason:       string;
}

export interface WorkStatusChange {
  event_type:   string;
  source:       string;
  triggered_by: string;
  reason:       string;
  changes:      Record<string, [string | number | null, string | number | null]>;
  at:           string;
}

export interface WorkStatusAssignment {
  assignment_id:             number;
  project_id:                number;
  project_code:              string;
  project_name:              string;
  role:                      string;
  work_mode:                 WorkMode;
  /** e.g. "Client Location (On-site)" */
  work_mode_display:         string;
  work_location:             string;
  notes:                     string;
  start_date:                string;
  end_date:                  string;
  assignment_status:         AssignmentStatus;
  assignment_status_display: string;
  is_current:                boolean;
  /** Current, but its start date is still ahead. */
  is_upcoming:               boolean;
  /** Days until the end date for a current assignment; null otherwise. */
  days_left:                 number | null;
  is_ending_soon:            boolean;
  last_change:               WorkStatusChange | null;
  change_log:                WorkStatusChange[];
}

export interface WorkStatusHistoryPage {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     WorkStatusAssignment[];
}

export interface WorkStatusResponse {
  employee_id:        string;
  employee_name:      string;
  employee_is_active: boolean;
  /** True when the viewer may assign, edit, extend and end this employee's projects (admins only). */
  can_manage:         boolean;
  current:            WorkStatusAssignment[];
  history:            WorkStatusHistoryPage;
}
