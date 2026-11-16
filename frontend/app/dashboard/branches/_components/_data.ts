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
  /** Valid coordinates that look wrong for the branch's state or city (advisory). */
  location_warnings?:    string[];
}

/** The Add/Edit Company Code form's values (inputs hold strings; ids as strings for <select>). */
export interface BranchForm {
  id:               number;
  branch_code:      string;
  branch_name:      string;
  address:          string;
  state:            string;
  city:             string;
  gst_registration: string;
  status:           string;
  is_headquarter:   boolean;
  is_metro:         boolean;
  geofencing_enabled:    boolean;
  latitude:              string;
  longitude:             string;
  allowed_radius_meters: string;
}

export const EMPTY_BRANCH_FORM: BranchForm = {
  id: 0, branch_code: "", branch_name: "", address: "", state: "", city: "", gst_registration: "",
  status: "active", is_headquarter: false, is_metro: false,
  geofencing_enabled: false, latitude: "", longitude: "", allowed_radius_meters: "150",
};

/** Maps a Company Code from GET /branch/branches/<id>/ onto the form. */
export function branchToForm(branch: Branch): BranchForm {
  return {
    id:               branch.id,
    branch_code:      branch.branch_code,
    branch_name:      branch.branch_name,
    address:          branch.address,
    state:            String(branch.state),
    city:             String(branch.city),
    gst_registration: branch.gst_registration ?? "",
    status:           branch.status.toLowerCase(),
    is_headquarter:   branch.is_headquarter,
    is_metro:         branch.is_metro ?? false,
    geofencing_enabled:    branch.geofencing_enabled ?? false,
    latitude:              branch.latitude?.toString() ?? "",
    longitude:             branch.longitude?.toString() ?? "",
    allowed_radius_meters: branch.allowed_radius_meters?.toString() ?? "150",
  };
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

/** A seat that carries branch-wide access — what a Company Code Admin is placed in. */
/** A position with branch-wide access. `holder` is the holder's User pk (= ApiEmployeeOption.uuid). */
export interface BranchAdminSeat {
  id: string; title: string; org_unit_name: string; holder_name: string | null;
  holder?: string | null;             // holder's User pk (= ApiEmployeeOption.uuid)
  holder_employee_id?: string | null; // holder's employee code (= ApiEmployeeOption.id)
}
export interface ApiEmployeeOption {
  id: string; uuid: string; employee_id: string; full_name: string; email: string; branch: string;
  is_active?: boolean;
}

/** The employee in a Company Code who holds a branch-wide-access position today, with that position. */
export interface CurrentBranchAdmin {
  employee:      ApiEmployeeOption;
  positionId:    string;
  positionTitle: string;
}

export interface LeaderForm {
  // "new" invites a brand-new person via the same create-and-email-credentials
  // flow as the Employees page, placed in a seat that carries branch-wide access; "existing" instead moves an
  // employee who's already in the company to this branch (a transfer, not a new hire).
  mode: "new" | "existing";
  name: string; email: string; positionId: string;
  employeeId: string; search: string;
}
export const EMPTY_LEADER: LeaderForm = {
  mode: "new", name: "", email: "", positionId: "",
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
