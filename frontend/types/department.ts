// Department — shared shapes for /api/departments/. Previously re-declared
// locally in ~5 files (hooks/useDepartmentOptions.ts, settings/departments,
// announcements, leave-policy eligibility, employee onboarding/creation) —
// consolidated here as part of Phase 3 Stage 5 (see frontend/TEAMCONTEXT.md).

// Lightweight reference shape — what a picker/dropdown needs.
export interface DepartmentOption {
  id:   number;
  name: string;
}

// Full shape — what the Settings → Departments management page needs.
export interface RoleInfo {
  name:         string;
  display_name: string;
}

export interface Department extends DepartmentOption {
  description:       string;
  is_active:         boolean;
  created_at:        string;
  designation_count: number;
  employee_count:    number;
  roles:             RoleInfo[];
}
