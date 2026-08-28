// Designation — shared shapes for /api/designations/. Previously
// re-declared locally in several files as ApiDesig/DesignationOption —
// consolidated here as part of Phase 3 Stage 5 (see frontend/TEAMCONTEXT.md).

// Lightweight reference shape — what a picker/dropdown needs. Some callers
// (candidate onboarding, add-employee) also want the parent department's
// name alongside it for display, so it's included but optional.
export interface DesignationOption {
  id:               number;
  name:             string;
  department_name?: string;
}

// Full shape — what the Settings → Departments management page needs
// (a Designation always belongs to exactly one Department there).
export interface Designation extends DesignationOption {
  department:      number;
  department_name: string;
  is_active:       boolean;
}
