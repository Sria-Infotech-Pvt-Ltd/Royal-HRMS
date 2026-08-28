// Org Structure — org units (a real hierarchy), positions (seats within a
// unit, possibly vacant), and job templates (a reusable title+band picked
// when creating a position). Deliberately independent of the employee
// directory's own department/reporting_manager fields — see
// backend/apps/accounts/models.py's OrgUnit/Position docstrings.

export interface OrgUnit {
  id:              string;
  name:            string;
  code:            string;
  parent:          string | null;
  cost_center:     string;
  is_active:       boolean;
  // Marks this unit as representing a real "department" for eligibility/
  // reporting purposes (LeavePolicy eligibility, attendance/dashboard
  // department filters) — see the backend's
  // services_approval.resolve_employee_department_name(), which walks up
  // to the nearest unit marked this way.
  is_department_level: boolean;
  position_count:  number;
  child_count:     number;
  created_at:      string;
  updated_at:      string;
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

export interface PositionScheduled {
  placement_id:   string;
  employee_name:  string;
  effective_from: string;
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
  is_active:           boolean;
  // holder/holder_name/holder_employee_id/holder_since are all derived from
  // whichever Placement currently covers "today" (or ?asOf=), not a stored
  // field — same field names as before on purpose, so most consumers of
  // this type need no changes.
  holder:              string | null;
  holder_name:         string | null;
  holder_employee_id:  string | null;
  holder_since:        string | null;
  // The next upcoming (future-dated) placement on this seat, if any —
  // doesn't affect who the current holder is.
  scheduled:           PositionScheduled | null;
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

export type PlacementStatus = "current" | "scheduled" | "ended";

export interface Placement {
  id:                    string;
  position:              string;
  employee:              string;
  employee_name:         string;
  employee_employee_id:  string;
  effective_from:        string;
  effective_to:          string | null;
  note:                  string;
  status:                PlacementStatus;
  created_at:            string;
  created_by:            string | null;
  created_by_name:       string | null;
  updated_at:            string;
}

export interface PlacementPayload {
  employee:        string;
  effective_from:  string;
  effective_to?:   string | null;
  note?:           string;
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
