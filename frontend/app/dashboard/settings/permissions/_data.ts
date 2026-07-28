// ─── API Types ────────────────────────────────────────────────────────────────

export interface ApiRole {
  id: number;
  name: string;           // slug, e.g. "hr_admin"
  display_name: string;   // human, e.g. "HR Admin"
  is_active: boolean;
  can_manage_team: boolean;
  user_count: number;
  permissions: string[];  // codenames, e.g. ["employees.view", "employees.create"]
}

export interface ApiPermission {
  id: number;
  codename: string; // e.g. "employees.view"
  module: string;   // e.g. "employees"
  action: string;   // e.g. "view"
}

/** GET /api/permissions/ response data — keyed by module name */
export type PermissionsMap = Record<string, ApiPermission[]>;

// ─── Form Types ───────────────────────────────────────────────────────────────

export interface RoleForm {
  display_name: string;
  can_manage_team: boolean;
  permission_codenames: string[];
}

export type RoleFormErrors = Partial<Record<keyof RoleForm, string>>;

export const EMPTY_ROLE_FORM: RoleForm = {
  display_name: "",
  can_manage_team: false,
  permission_codenames: [],
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Convert a display name to a snake_case API name slug */
export function slugifyName(displayName: string): string {
  return displayName
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_]/g, "");
}

/** All permissions a role has for a given module (returns action names only) */
export function actionsForModule(role: ApiRole, module: string): string[] {
  return role.permissions
    .filter(p => p.startsWith(module + "."))
    .map(p => p.split(".")[1]);
}

/** Badge class for a role's active state */
export function activeBadgeClass(isActive: boolean): string {
  return isActive ? "badge badge-success" : "badge badge-neutral";
}

/** Badge class for a single permission action cell */
export function permCellClass(hasPerms: boolean): string {
  return hasPerms ? "badge badge-success" : "badge badge-neutral";
}

/** Module display name capitalised */
export function moduleDisplayName(module: string): string {
  const overrides: Record<string, string> = {
    employees:     "Employees",
    recruitment:   "Recruitment",
    attendance:    "Attendance",
    leave:         "Leave",
    payroll:       "Payroll",
    expenses:      "Expenses",
    referrals:     "Referrals",
    announcements: "Announcements",
    documents:     "Documents",
    settings:      "Settings",
    reports:       "Reports",
    audit:         "Audit",
  };
  return overrides[module] ?? module.charAt(0).toUpperCase() + module.slice(1);
}

// ─── Permission Presets ───────────────────────────────────────────────────────

export interface PermissionPreset {
  key:         string;
  label:       string;
  icon:        string;
  description: string;
  /** Return true for every codename that should be selected by this preset */
  match: (codename: string) => boolean;
}

export const PERMISSION_PRESETS: PermissionPreset[] = [
  {
    key:         "full_admin",
    label:       "Full Admin",
    icon:        "ti-shield-check",
    description: "All permissions across every module",
    match:       () => true,
  },
  {
    key:         "view_only",
    label:       "View Only",
    icon:        "ti-eye",
    description: "Read-only access to all modules — no create, edit or delete",
    match:       c => c.endsWith(".view"),
  },
  {
    key:         "manager",
    label:       "Manager",
    icon:        "ti-users",
    description: "Team HR: view and approve across core modules",
    match:       c => ([
      "employees.view",
      "attendance.view", "attendance.create", "attendance.edit",
      "leave.view",      "leave.approve",
      "expenses.view",   "expenses.approve",
      "documents.view",  "documents.create",
      "announcements.view",
      "recruitment.view",
      "reports.view",
    ] as string[]).includes(c),
  },
  {
    key:         "employee",
    label:       "Employee",
    icon:        "ti-user",
    description: "Self-service: leave, expenses, documents, referrals",
    match:       c => {
      const selfModules = ["leave", "expenses", "documents", "announcements", "referrals"];
      const [module, action] = c.split(".");
      return selfModules.includes(module) && ["view", "create"].includes(action);
    },
  },
];

export function validateRoleForm(form: RoleForm): RoleFormErrors {
  const errors: RoleFormErrors = {};
  if (!form.display_name.trim())        errors.display_name        = "Role name is required";
  if (!form.permission_codenames.length) errors.permission_codenames = "Select at least one permission";
  return errors;
}
