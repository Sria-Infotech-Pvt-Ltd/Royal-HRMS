// Work Status: project assignments synced from Project Budgeting. Status values are plain strings because Project
// Budgeting may add new ones without notice — the *_display fields are the labels to show.

export interface WorkStatusChange {
  event_type:   string;
  source:       string;
  triggered_by: string;
  changes:      Record<string, [string | number | null, string | number | null]>;
  at:           string;
}

export interface WorkStatusAssignment {
  assignment_id:             number;
  project_id:                number;
  project_code:              string;
  project_name:              string;
  project_status:            string;
  project_status_display:    string;
  milestone_name:            string;
  role:                      string;
  allocation_percent:        string | null;
  start_date:                string | null;
  end_date:                  string | null;
  is_ongoing:                boolean;
  assignment_status:         string;
  assignment_status_display: string;
  is_current:                boolean;
  last_change:               WorkStatusChange | null;
  change_log:                WorkStatusChange[];
}

export interface WorkStatusConflict {
  type:    string;
  message: string;
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
  managed_in:         string;
  is_read_only:       boolean;
  last_synced_at:     string | null;
  current:            WorkStatusAssignment[];
  conflicts:          WorkStatusConflict[];
  history:            WorkStatusHistoryPage;
}

export interface ProjectSyncLogRow {
  source:       string;
  triggered_by: string;
  employee_id:  string;
  status:       "success" | "failed" | "unmatched";
  saved:        number;
  changed:      number;
  removed:      number;
  message:      string;
  at:           string;
}

export interface ProjectSyncStatus {
  is_pull_configured:     boolean;
  last_synced_at:         string | null;
  failed_last_24h:        number;
  unmatched_employee_ids: string[];
  open_assignments:       number;
  logs: {
    count:       number;
    page:        number;
    page_size:   number;
    total_pages: number;
    results:     ProjectSyncLogRow[];
  };
}
