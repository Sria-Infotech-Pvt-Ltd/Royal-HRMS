// Field names mirror the raw API response (snake_case), matching the
// existing ApiEmployee/ApiProfile convention in employees/[id]/page.tsx —
// no separate camelCase mapping layer for a shape this small.
export interface OrgChartPerson {
  id:          string;
  employee_id: string;
  name:        string;
  designation: string;
}

export interface OrgChartDepartment {
  id:      number;
  label:   string;
  head:    OrgChartPerson | null;
  members: OrgChartPerson[];
}

// One branch's tree. A real multi-branch company has a different manager
// (and often the same department name) per branch, so the chart is always a
// list of these — never one flat structure merging branches together.
export interface OrgChartGroup {
  branch:      string;
  root:        OrgChartPerson | null;
  departments: OrgChartDepartment[];
}

export interface OrgChartData {
  // "company" = viewer can pick any branch (or "All Branches") via the
  // dropdown — the dropdown's own options come from the existing branches
  // list endpoint (lib/api/endpoints.ts branches.list), not from here, so
  // there's exactly one place in the app that answers "what branches exist."
  // "branch" = viewer is permanently scoped to their own branch — `groups`
  // always has exactly one entry.
  scope:  "company" | "branch";
  groups: OrgChartGroup[];
}
