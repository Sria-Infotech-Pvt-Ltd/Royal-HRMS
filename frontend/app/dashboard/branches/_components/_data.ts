// Pure types/constants/helpers for the Branches (Company Codes) module — no
// component state, safe to import from anywhere in this folder.

export interface StateObj {
  id: number;
  name: string;
}

export interface CityObj {
  id: number;
  name: string;
}

export interface Branch {
  id:             number;
  branch_code:    string;
  branch_name:    string;
  is_headquarter: boolean;
  is_metro:       boolean;
  address:        string;
  state:          number;
  state_name:     string;
  city:           number;
  city_name:      string;
  gst_registration:       string | null;
  gst_registration_gstin: string | null;
  employees_count: number;
  status:         string;
  geofencing_enabled:    boolean;
  latitude:              number | null;
  longitude:             number | null;
  allowed_radius_meters: number | null;
  has_coordinates:       boolean;
}

export function geofenceBadge(branch: Branch): { label: string; cls: string } {
  if (!branch.geofencing_enabled) return { label: "Disabled", cls: "badge-neutral" };
  if (!branch.has_coordinates)    return { label: "No Coordinates", cls: "badge-warn" };
  return { label: "Active", cls: "badge-success" };
}

export interface BranchStats {
  total_branches:          number;
  total_employees:         number;
  total_active_branches:   number;
  total_inactive_branches: number;
  total_cities:            number;
}

export interface BranchDistribution {
  branch:      string;
  branch_code: string;
  employees:   number;
}

export type Envelope<T> = { status: string; message: string; data: T };
export type Paginated<T> = { count: number; page: number; page_size: number; total_pages: number; results: T[] };

export interface ApiRole {
  id: number; name: string; display_name: string;
  can_manage_branch: boolean; permissions: string[];
}
export interface ApiEmployeeOption {
  id: string; uuid: string; employee_id: string; full_name: string; email: string; branch: string; role: string;
}

export interface LeaderForm {
  // "new" invites a brand-new person via the same create-and-email-credentials
  // flow as the Employees page; "existing" instead re-roles/re-branches an
  // employee who's already in the company (a transfer, not a new hire).
  // No department field — a Branch Admin oversees every department in the
  // branch, not one, unlike every other role.
  mode: "new" | "existing";
  name: string; email: string; designation: string;
  employeeId: string; search: string;
}
export const EMPTY_LEADER: LeaderForm = {
  mode: "new", name: "", email: "", designation: "Branch Manager",
  employeeId: "", search: "",
};

// A leader row counts as "in use" the moment it's touched — once it is,
// every field that mode needs becomes required together.
export function isLeaderActive(f: LeaderForm): boolean {
  return f.mode === "existing"
    ? !!f.employeeId
    : !!(f.name.trim() || f.email.trim());
}

export const EMAIL_RE = /^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/;

export const OTHER_CITY = "__other__";
export const BRANCH_NAME_RE = /^[A-Za-z0-9](?:[A-Za-z0-9 &\-.]*[A-Za-z0-9])?$/;
export const CITY_NAME_RE   = /^[A-Za-z]+(?:[ '-][A-Za-z]+)*$/;
