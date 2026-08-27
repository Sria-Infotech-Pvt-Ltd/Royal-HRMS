// Org Structure — org units (a real hierarchy), positions (seats within a
// unit, possibly vacant), and job templates (a reusable title+band picked
// when creating a position). Deliberately independent of the employee
// directory's own department/reporting_manager fields — see
// backend/apps/accounts/models.py's OrgUnit/Position docstrings.

export interface OrgUnit {
  id:             string;
  name:           string;
  code:           string;
  parent:         string | null;
  cost_center:    string;
  position_count: number;
  child_count:    number;
  created_at:     string;
  updated_at:     string;
}

export interface JobTemplate {
  id:   string;
  name: string;
  band: string;
}

export interface PositionReportsTo {
  position_id: string;
  title:       string;
  holder_name: string | null;
}

export interface Position {
  id:                  string;
  org_unit:            string;
  org_unit_name:       string;
  job_template:        string | null;
  job_template_name:   string | null;
  title:               string;
  grade:               string;
  is_chief:            boolean;
  holder:              string | null;
  holder_name:         string | null;
  holder_employee_id:  string | null;
  // Optional — most positions sit in the one shared, company-wide tree;
  // set only when a seat is genuinely tied to one physical branch. Lets
  // the same tree be filtered to a branch-specific view (?branch=<id>)
  // without duplicating OrgUnit/Position data per branch.
  branch:              number | null;
  branch_name:         string | null;
  reports_to:          PositionReportsTo | null;
  created_at:           string;
  updated_at:           string;
}

export interface OrgUnitPayload {
  name:        string;
  code:        string;
  parent:      string | null;
  cost_center: string;
}

export interface PositionPayload {
  org_unit:     string;
  job_template: string | null;
  title:        string;
  grade:        string;
  is_chief:     boolean;
  branch?:      number | null;
}
